# PrimeKG Differential Diagnosis Hypothesis Engine
## Comprehensive Design Document for Forge V3 Integration

**Version:** 1.0.0
**Date:** January 2026
**Status:** Design Phase

---

## Executive Summary

This document outlines the complete architecture for integrating PrimeKG (Precision Medicine Knowledge Graph) into Forge V3 as an overlay, creating an autonomous differential diagnosis hypothesis engine. The system will leverage:

- **129,375 PrimeKG nodes** across 10 biological entity types
- **4,050,249 relationships** across 30 edge types
- **HPO-based phenotype pipelines** for symptom-to-disease mapping
- **Multi-agent diagnostic reasoning** with interruptable Q&A
- **Full medical history integration** with wearable data conversion
- **Compliance with HIPAA, GDPR, and Forge's 400+ control framework**

---

## Table of Contents

1. [PrimeKG Schema Mapping](#1-primekg-schema-mapping)
2. [PrimeKG Overlay Architecture](#2-primekg-overlay-architecture)
3. [Differential Diagnosis Hypothesis Engine](#3-differential-diagnosis-hypothesis-engine)
4. [Autonomous Operation Flow](#4-autonomous-operation-flow)
5. [Medical History Data Model](#5-medical-history-data-model)
6. [HPO-Based Phenotype Pipeline](#6-hpo-based-phenotype-pipeline)
7. [Genetic Data Handling](#7-genetic-data-handling)
8. [Multi-Agent Diagnostic System](#8-multi-agent-diagnostic-system)
9. [Wearable Data Conversion](#9-wearable-data-conversion)
10. [Compliance Framework Alignment](#10-compliance-framework-alignment)
11. [Implementation Roadmap](#11-implementation-roadmap)

---

## 1. PrimeKG Schema Mapping

### 1.1 PrimeKG Node Types → Forge Capsule Types

| PrimeKG Node Type | Forge CapsuleType | Description |
|-------------------|-------------------|-------------|
| Disease | `KNOWLEDGE` | MONDO ontology disease entities |
| Gene/Protein | `KNOWLEDGE` | Entrez Gene identifiers |
| Drug | `KNOWLEDGE` | DrugBank compound data |
| Phenotype/Effect | `INSIGHT` | HPO-encoded phenotypes |
| Anatomy | `KNOWLEDGE` | UBERON anatomical structures |
| Biological Process | `KNOWLEDGE` | GO biological processes |
| Molecular Function | `KNOWLEDGE` | GO molecular functions |
| Cellular Component | `KNOWLEDGE` | GO cellular components |
| Pathway | `KNOWLEDGE` | Reactome pathways |
| Exposure | `WARNING` | Environmental/clinical exposures |

### 1.2 Neo4j Schema Extensions

```cypher
// PrimeKG Node Labels
CREATE CONSTRAINT primekg_disease_id IF NOT EXISTS
FOR (d:PrimeKGDisease) REQUIRE d.mondo_id IS UNIQUE;

CREATE CONSTRAINT primekg_gene_id IF NOT EXISTS
FOR (g:PrimeKGGene) REQUIRE g.entrez_id IS UNIQUE;

CREATE CONSTRAINT primekg_drug_id IF NOT EXISTS
FOR (d:PrimeKGDrug) REQUIRE d.drugbank_id IS UNIQUE;

CREATE CONSTRAINT primekg_phenotype_id IF NOT EXISTS
FOR (p:PrimeKGPhenotype) REQUIRE p.hpo_id IS UNIQUE;

// Vector index for semantic search on PrimeKG descriptions
CREATE VECTOR INDEX primekg_embedding_index IF NOT EXISTS
FOR (n:PrimeKGNode)
ON n.embedding
OPTIONS {
    indexConfig: {
        `vector.dimensions`: 1536,
        `vector.similarity_function`: 'cosine'
    }
}

// Full-text index for clinical descriptions
CREATE FULLTEXT INDEX primekg_description_index IF NOT EXISTS
FOR (n:PrimeKGNode) ON EACH [n.description, n.clinical_notes]
```

### 1.3 PrimeKG Edge Types → Forge Semantic Edges

| PrimeKG Relation | Forge SemanticEdgeType | Confidence Weight |
|------------------|------------------------|-------------------|
| indication | `SUPPORTS` | 0.95 |
| contraindication | `CONTRADICTS` | 0.95 |
| off_label_use | `REFERENCES` | 0.70 |
| disease_phenotype | `ELABORATES` | 0.90 |
| drug_target | `REFERENCES` | 0.85 |
| gene_disease | `SUPPORTS` | 0.80 |
| pathway_involvement | `ELABORATES` | 0.75 |

### 1.4 Data Import Pipeline

```python
# forge/services/primekg_import.py

class PrimeKGImportService:
    """Service for importing PrimeKG data into Forge Neo4j."""

    PRIMEKG_DATAVERSE_URL = "https://dataverse.harvard.edu/api/access/datafile/6180620"

    async def import_nodes(self, nodes_csv_path: str) -> ImportResult:
        """
        Import PrimeKG nodes as Forge capsules with PrimeKG labels.

        CSV columns: node_index, node_id, node_type, node_name, node_source
        """
        ...

    async def import_edges(self, edges_csv_path: str) -> ImportResult:
        """
        Import PrimeKG edges as Forge semantic relationships.

        CSV columns: relation, x_index, y_index
        """
        ...

    async def enrich_with_embeddings(self, batch_size: int = 100) -> int:
        """Generate embeddings for PrimeKG clinical descriptions."""
        ...
```

---

## 2. PrimeKG Overlay Architecture

### 2.1 Overlay Implementation

```python
# forge/overlays/primekg_overlay.py

from typing import Any
from .base import BaseOverlay, OverlayContext, OverlayResult
from ..models.events import Event, EventType
from ..models.overlay import Capability
from ..models.base import TrustLevel

class PrimeKGOverlay(BaseOverlay):
    """
    PrimeKG Biomedical Knowledge Graph Overlay.

    Provides:
    - Disease-phenotype mapping via HPO
    - Drug-disease relationship queries
    - Gene-disease association lookups
    - Pathway analysis for mechanism understanding
    - Clinical description semantic search
    """

    NAME = "primekg"
    VERSION = "1.0.0"
    DESCRIPTION = "Precision Medicine Knowledge Graph integration for diagnostic support"

    SUBSCRIBED_EVENTS = {
        EventType.CAPSULE_CREATED,
        EventType.CAPSULE_UPDATED,
        EventType.CASCADE_INITIATED,
        EventType.INSIGHT_GENERATED,
    }

    REQUIRED_CAPABILITIES = {
        Capability.DATABASE_READ,
        Capability.DATABASE_WRITE,
        Capability.EVENT_PUBLISH,
        Capability.LLM_ACCESS,
    }

    MIN_TRUST_LEVEL = TrustLevel.TRUSTED  # Medical data requires higher trust

    DEFAULT_FUEL_BUDGET = FuelBudget(
        function_name="primekg_query",
        max_fuel=5_000_000,
        max_memory_bytes=100 * 1024 * 1024,  # 100MB for graph traversals
        timeout_ms=60000  # 60s for complex queries
    )

    def __init__(self, neo4j_client=None, embedding_service=None):
        super().__init__()
        self._neo4j = neo4j_client
        self._embedding = embedding_service
        self._hpo_hierarchy = None  # Cached HPO DAG
        self._disease_phenotype_cache = {}

    async def initialize(self) -> bool:
        """Initialize PrimeKG overlay with HPO hierarchy preload."""
        self._logger.info("primekg_initializing")

        # Preload HPO hierarchy for fast phenotype traversal
        self._hpo_hierarchy = await self._load_hpo_hierarchy()

        # Verify PrimeKG data is loaded
        stats = await self._verify_primekg_data()
        if stats["disease_count"] < 10000:
            self._logger.warning("primekg_data_incomplete", stats=stats)

        return await super().initialize()

    async def execute(
        self,
        context: OverlayContext,
        event: Event | None = None,
        input_data: dict[str, Any] | None = None
    ) -> OverlayResult:
        """Execute PrimeKG knowledge enrichment."""

        data = input_data or {}
        if event:
            data.update(event.payload or {})

        operation = data.get("operation", "enrich")

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
            else:
                result = await self._semantic_enrich(data, context)

            return OverlayResult.ok(
                data=result,
                events_to_emit=[
                    self.create_event_emission(
                        EventType.INSIGHT_GENERATED,
                        {"source": "primekg", "operation": operation, "result_count": len(result.get("results", []))}
                    )
                ]
            )
        except Exception as e:
            self._logger.error("primekg_execution_error", error=str(e))
            return OverlayResult.fail(f"PrimeKG error: {str(e)}")

    async def _phenotype_to_disease(
        self,
        data: dict,
        context: OverlayContext
    ) -> dict:
        """
        Map phenotypes (HPO terms) to candidate diseases.

        Uses IC (Information Content) scoring for phenotype-disease matching.
        """
        hpo_ids = data.get("phenotypes", [])

        query = """
        UNWIND $hpo_ids AS hpo_id
        MATCH (p:PrimeKGPhenotype {hpo_id: hpo_id})-[:PHENOTYPE_OF]->(d:PrimeKGDisease)
        WITH d, collect(p.hpo_id) as matched_phenotypes, count(p) as match_count
        MATCH (d)-[:PHENOTYPE_OF]-(all_p:PrimeKGPhenotype)
        WITH d, matched_phenotypes, match_count, count(all_p) as total_phenotypes
        RETURN d.mondo_id as disease_id,
               d.name as disease_name,
               d.description as description,
               matched_phenotypes,
               match_count,
               total_phenotypes,
               toFloat(match_count) / size($hpo_ids) as recall,
               toFloat(match_count) / total_phenotypes as precision
        ORDER BY recall * precision DESC
        LIMIT 20
        """

        results = await self._neo4j.run(query, {"hpo_ids": hpo_ids})

        return {
            "operation": "phenotype_to_disease",
            "input_phenotypes": hpo_ids,
            "results": [
                {
                    "disease_id": r["disease_id"],
                    "disease_name": r["disease_name"],
                    "description": r["description"],
                    "matched_phenotypes": r["matched_phenotypes"],
                    "score": r["recall"] * r["precision"],
                    "recall": r["recall"],
                    "precision": r["precision"]
                }
                for r in results
            ]
        }

    async def _differential_diagnosis(
        self,
        data: dict,
        context: OverlayContext
    ) -> dict:
        """
        Generate differential diagnosis from phenotypes and clinical context.

        Combines:
        - HPO phenotype matching
        - Gene associations (if genetic data available)
        - Drug history (for contraindications)
        - Pathway analysis (for mechanism support)
        """
        phenotypes = data.get("phenotypes", [])
        genes = data.get("genes", [])
        medications = data.get("medications", [])

        # Phase 1: Phenotype-based candidates
        phenotype_candidates = await self._phenotype_to_disease(
            {"phenotypes": phenotypes}, context
        )

        # Phase 2: Gene association boost (if available)
        if genes:
            gene_associations = await self._gene_disease_boost(
                phenotype_candidates["results"], genes
            )
        else:
            gene_associations = phenotype_candidates["results"]

        # Phase 3: Medication contraindication filter
        if medications:
            filtered = await self._filter_contraindicated(
                gene_associations, medications
            )
        else:
            filtered = gene_associations

        # Phase 4: Rank by composite score
        ranked = self._rank_differential(filtered, phenotypes, genes)

        return {
            "operation": "differential_diagnosis",
            "input": {
                "phenotypes": phenotypes,
                "genes": genes,
                "medications": medications
            },
            "differential": ranked[:10],
            "evidence_summary": self._generate_evidence_summary(ranked[:10])
        }
```

### 2.2 Overlay Capabilities

```python
# Add to forge/models/overlay.py CORE_OVERLAY_CAPABILITIES

CORE_OVERLAY_CAPABILITIES = {
    # ... existing overlays ...

    "primekg": {
        Capability.DATABASE_READ,
        Capability.DATABASE_WRITE,
        Capability.EVENT_PUBLISH,
        Capability.EVENT_SUBSCRIBE,
        Capability.LLM_ACCESS,
        Capability.CAPSULE_CREATE,
    },
}
```

---

## 3. Differential Diagnosis Hypothesis Engine

### 3.1 Core Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                 DIAGNOSIS HYPOTHESIS ENGINE                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Input      │  │   Phenotype  │  │   Genetic    │          │
│  │   Parser     │──│   Extractor  │──│   Analyzer   │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│         │                  │                  │                  │
│         ▼                  ▼                  ▼                  │
│  ┌─────────────────────────────────────────────────┐           │
│  │           HYPOTHESIS GENERATOR                   │           │
│  │  • PrimeKG Knowledge Grounding                  │           │
│  │  • Bayesian Probability Estimation               │           │
│  │  • Evidence Chain Construction                   │           │
│  └─────────────────────────────────────────────────┘           │
│         │                                                       │
│         ▼                                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  Hypothesis  │  │   Evidence   │  │   Ranking    │          │
│  │  Refinement  │──│   Scoring    │──│   Engine     │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│         │                                                       │
│         ▼                                                       │
│  ┌─────────────────────────────────────────────────┐           │
│  │           OUTPUT: RANKED DIFFERENTIAL            │           │
│  │  • Disease hypotheses with confidence scores     │           │
│  │  • Supporting evidence chains (Isnad)           │           │
│  │  • Recommended confirmatory tests                │           │
│  │  • Treatment pathway suggestions                 │           │
│  └─────────────────────────────────────────────────┘           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Hypothesis Data Model

```python
# forge/models/diagnosis.py

from enum import Enum
from pydantic import Field
from forge.models.base import ForgeModel, TimestampMixin

class DiagnosisConfidence(str, Enum):
    """Confidence levels for diagnostic hypotheses."""
    DEFINITIVE = "definitive"      # >95% confidence
    HIGHLY_LIKELY = "highly_likely"  # 80-95% confidence
    PROBABLE = "probable"          # 60-80% confidence
    POSSIBLE = "possible"          # 40-60% confidence
    UNLIKELY = "unlikely"          # <40% confidence

class EvidenceType(str, Enum):
    """Types of supporting evidence."""
    PHENOTYPE_MATCH = "phenotype_match"
    GENE_ASSOCIATION = "gene_association"
    PATHWAY_SUPPORT = "pathway_support"
    DRUG_RESPONSE = "drug_response"
    LAB_FINDING = "lab_finding"
    IMAGING_FINDING = "imaging_finding"
    FAMILY_HISTORY = "family_history"
    EPIDEMIOLOGY = "epidemiology"

class DiagnosticEvidence(ForgeModel):
    """Single piece of evidence supporting a hypothesis."""
    evidence_type: EvidenceType
    source_id: str  # PrimeKG node ID or capsule ID
    source_name: str
    description: str
    weight: float = Field(ge=0.0, le=1.0)
    is_contradictory: bool = False
    primekg_path: list[str] | None = None  # Graph path for lineage

class DiagnosticHypothesis(ForgeModel, TimestampMixin):
    """A single diagnostic hypothesis with evidence."""
    hypothesis_id: str
    disease_id: str  # MONDO ID
    disease_name: str
    icd10_codes: list[str] = []
    confidence: DiagnosisConfidence
    probability_score: float = Field(ge=0.0, le=1.0)

    # Evidence chain (Isnad)
    supporting_evidence: list[DiagnosticEvidence] = []
    contradicting_evidence: list[DiagnosticEvidence] = []

    # Actionable recommendations
    confirmatory_tests: list[str] = []
    differential_tests: list[str] = []  # Tests to rule out
    treatment_pathways: list[str] = []

    # PrimeKG grounding
    primekg_disease_node: str | None = None
    phenotype_overlap_score: float = 0.0
    gene_support_score: float = 0.0
    pathway_relevance_score: float = 0.0

class DifferentialDiagnosis(ForgeModel, TimestampMixin):
    """Complete differential diagnosis with ranked hypotheses."""
    session_id: str
    patient_id: str | None = None  # Anonymized

    # Input summary
    input_phenotypes: list[str] = []
    input_genes: list[str] = []
    input_medications: list[str] = []
    input_history: dict = {}

    # Hypotheses ranked by probability
    hypotheses: list[DiagnosticHypothesis] = []

    # Quality metrics
    total_evidence_pieces: int = 0
    primekg_nodes_traversed: int = 0
    computation_time_ms: float = 0.0

    # Autonomous operation state
    current_phase: str = "initial"
    questions_asked: int = 0
    is_complete: bool = False
```

### 3.3 Hypothesis Engine Service

```python
# forge/services/diagnosis_engine.py

class DiagnosisHypothesisEngine:
    """
    Autonomous differential diagnosis generator.

    Uses PrimeKG knowledge graph to ground hypotheses in
    biomedical evidence with full lineage tracking.
    """

    def __init__(
        self,
        primekg_overlay: PrimeKGOverlay,
        llm_service: LLMService,
        phenotype_pipeline: HPOPhenotypePipeline,
        genetic_handler: GeneticDataHandler,
    ):
        self.primekg = primekg_overlay
        self.llm = llm_service
        self.phenotypes = phenotype_pipeline
        self.genetics = genetic_handler

        # Bayesian prior probabilities from epidemiology
        self._disease_priors = {}

    async def generate_differential(
        self,
        session_id: str,
        input_data: DiagnosisInput,
        max_hypotheses: int = 10,
    ) -> DifferentialDiagnosis:
        """
        Generate ranked differential diagnosis from clinical input.

        Pipeline:
        1. Extract/normalize phenotypes to HPO
        2. Query PrimeKG for phenotype-disease associations
        3. Incorporate genetic data if available
        4. Calculate Bayesian posterior probabilities
        5. Construct evidence chains (Isnad)
        6. Rank by composite score
        """
        start_time = time.time()

        # Phase 1: Phenotype normalization
        hpo_phenotypes = await self.phenotypes.extract_and_normalize(
            input_data.symptoms,
            input_data.clinical_notes
        )

        # Phase 2: Initial hypothesis generation
        primekg_result = await self.primekg.execute(
            context=self._create_context(),
            input_data={
                "operation": "differential_diagnosis",
                "phenotypes": hpo_phenotypes,
                "genes": input_data.genetic_markers,
                "medications": input_data.current_medications,
            }
        )

        # Phase 3: Bayesian scoring
        hypotheses = []
        for candidate in primekg_result.data["differential"]:
            # Calculate prior from epidemiology
            prior = self._get_disease_prior(candidate["disease_id"])

            # Calculate likelihood from phenotype overlap
            likelihood = self._calculate_phenotype_likelihood(
                candidate, hpo_phenotypes
            )

            # Bayesian posterior
            posterior = self._bayesian_update(prior, likelihood)

            # Build evidence chain
            evidence = await self._build_evidence_chain(
                candidate, hpo_phenotypes, input_data
            )

            hypothesis = DiagnosticHypothesis(
                hypothesis_id=str(uuid4()),
                disease_id=candidate["disease_id"],
                disease_name=candidate["disease_name"],
                confidence=self._score_to_confidence(posterior),
                probability_score=posterior,
                supporting_evidence=evidence["supporting"],
                contradicting_evidence=evidence["contradicting"],
                confirmatory_tests=await self._suggest_confirmatory_tests(candidate),
                primekg_disease_node=candidate["disease_id"],
                phenotype_overlap_score=candidate["recall"],
                gene_support_score=candidate.get("gene_score", 0.0),
            )
            hypotheses.append(hypothesis)

        # Sort by probability
        hypotheses.sort(key=lambda h: h.probability_score, reverse=True)

        return DifferentialDiagnosis(
            session_id=session_id,
            input_phenotypes=hpo_phenotypes,
            input_genes=input_data.genetic_markers,
            input_medications=input_data.current_medications,
            hypotheses=hypotheses[:max_hypotheses],
            total_evidence_pieces=sum(
                len(h.supporting_evidence) + len(h.contradicting_evidence)
                for h in hypotheses
            ),
            primekg_nodes_traversed=primekg_result.data.get("nodes_traversed", 0),
            computation_time_ms=(time.time() - start_time) * 1000,
            current_phase="complete",
            is_complete=True,
        )
```

---

## 4. Autonomous Operation Flow

### 4.1 State Machine

```
┌─────────────┐
│   IDLE      │
└──────┬──────┘
       │ start_session()
       ▼
┌─────────────┐
│   INTAKE    │◄───────────────────────┐
└──────┬──────┘                        │
       │ initial_input                 │
       ▼                               │
┌─────────────┐     interrupt()   ┌────┴────┐
│  ANALYZING  │◄─────────────────►│ PAUSED  │
└──────┬──────┘                   └─────────┘
       │ need_more_info?
       ├────────yes────────┐
       │                   ▼
       │           ┌─────────────┐
       │           │ QUESTIONING │──────────┐
       │           └──────┬──────┘          │
       │                  │ answer          │ timeout
       │                  ▼                 │
       │           ┌─────────────┐          │
       │           │  REFINING   │          │
       │           └──────┬──────┘          │
       │                  │                 │
       └──────────────────┴─────────────────┘
       │ complete
       ▼
┌─────────────┐
│  COMPLETE   │
└──────┬──────┘
       │ new_info
       ▼
┌─────────────┐
│  UPDATING   │───────► back to COMPLETE
└─────────────┘
```

### 4.2 Autonomous Session Controller

```python
# forge/services/diagnosis_session.py

class DiagnosisSessionState(str, Enum):
    IDLE = "idle"
    INTAKE = "intake"
    ANALYZING = "analyzing"
    QUESTIONING = "questioning"
    REFINING = "refining"
    PAUSED = "paused"
    COMPLETE = "complete"
    UPDATING = "updating"

class DiagnosisSession(ForgeModel, TimestampMixin):
    """Stateful diagnosis session with interruptable operation."""

    session_id: str
    state: DiagnosisSessionState = DiagnosisSessionState.IDLE

    # Patient data (accumulated)
    symptoms: list[str] = []
    phenotypes: list[str] = []  # HPO-normalized
    medical_history: dict = {}
    genetic_data: dict = {}
    wearable_data: dict = {}
    medications: list[str] = []

    # Conversation history
    questions_asked: list[dict] = []
    answers_received: list[dict] = []

    # Current analysis
    current_differential: DifferentialDiagnosis | None = None
    confidence_threshold: float = 0.7

    # Control flags
    is_interrupted: bool = False
    awaiting_answer: bool = False
    max_questions: int = 10
    question_count: int = 0

class AutonomousDiagnosisController:
    """
    Controls autonomous diagnosis flow with interruptable Q&A.

    The engine operates autonomously after initial input,
    asking follow-up questions only when needed to improve
    diagnostic confidence.
    """

    def __init__(
        self,
        hypothesis_engine: DiagnosisHypothesisEngine,
        llm_service: LLMService,
        session_store: SessionStore,
    ):
        self.engine = hypothesis_engine
        self.llm = llm_service
        self.sessions = session_store

    async def start_session(
        self,
        initial_symptoms: list[str],
        medical_history: dict | None = None,
    ) -> DiagnosisSession:
        """Start new autonomous diagnosis session."""
        session = DiagnosisSession(
            session_id=str(uuid4()),
            state=DiagnosisSessionState.INTAKE,
            symptoms=initial_symptoms,
            medical_history=medical_history or {},
        )
        await self.sessions.save(session)
        return session

    async def process(
        self,
        session_id: str,
        new_input: dict | None = None,
    ) -> DiagnosisSessionResponse:
        """
        Process session step.

        Called repeatedly until session reaches COMPLETE state.
        Can be interrupted at any point via interrupt().
        """
        session = await self.sessions.get(session_id)

        if session.is_interrupted:
            session.state = DiagnosisSessionState.PAUSED
            return DiagnosisSessionResponse(
                session=session,
                status="paused",
                message="Session paused. Call resume() to continue.",
            )

        # Handle new input (answer to question)
        if new_input and session.awaiting_answer:
            await self._process_answer(session, new_input)
            session.awaiting_answer = False

        # State machine transitions
        if session.state == DiagnosisSessionState.INTAKE:
            return await self._handle_intake(session)

        elif session.state == DiagnosisSessionState.ANALYZING:
            return await self._handle_analyzing(session)

        elif session.state == DiagnosisSessionState.QUESTIONING:
            return await self._handle_questioning(session)

        elif session.state == DiagnosisSessionState.REFINING:
            return await self._handle_refining(session)

        elif session.state == DiagnosisSessionState.COMPLETE:
            return DiagnosisSessionResponse(
                session=session,
                status="complete",
                differential=session.current_differential,
            )

        return DiagnosisSessionResponse(
            session=session,
            status="unknown_state",
        )

    async def _handle_analyzing(
        self,
        session: DiagnosisSession
    ) -> DiagnosisSessionResponse:
        """Run hypothesis engine and decide next step."""

        # Generate initial differential
        differential = await self.engine.generate_differential(
            session_id=session.session_id,
            input_data=DiagnosisInput(
                symptoms=session.symptoms,
                genetic_markers=list(session.genetic_data.keys()),
                current_medications=session.medications,
                medical_history=session.medical_history,
            )
        )
        session.current_differential = differential

        # Decide: complete or need more info?
        top_hypothesis = differential.hypotheses[0] if differential.hypotheses else None

        if top_hypothesis and top_hypothesis.probability_score >= session.confidence_threshold:
            # High confidence - complete
            session.state = DiagnosisSessionState.COMPLETE
            await self.sessions.save(session)
            return DiagnosisSessionResponse(
                session=session,
                status="complete",
                differential=differential,
            )

        # Low confidence - generate discriminating question
        if session.question_count < session.max_questions:
            question = await self._generate_discriminating_question(
                session, differential
            )
            session.state = DiagnosisSessionState.QUESTIONING
            session.awaiting_answer = True
            session.questions_asked.append(question)
            session.question_count += 1
            await self.sessions.save(session)

            return DiagnosisSessionResponse(
                session=session,
                status="questioning",
                question=question,
                current_differential=differential,
            )

        # Max questions reached - complete with current confidence
        session.state = DiagnosisSessionState.COMPLETE
        await self.sessions.save(session)
        return DiagnosisSessionResponse(
            session=session,
            status="complete",
            differential=differential,
            note="Maximum questions reached",
        )

    async def interrupt(self, session_id: str) -> bool:
        """Interrupt current session (user can resume later)."""
        session = await self.sessions.get(session_id)
        session.is_interrupted = True
        await self.sessions.save(session)
        return True

    async def resume(self, session_id: str) -> DiagnosisSessionResponse:
        """Resume interrupted session."""
        session = await self.sessions.get(session_id)
        session.is_interrupted = False
        session.state = DiagnosisSessionState.ANALYZING
        await self.sessions.save(session)
        return await self.process(session_id)

    async def _generate_discriminating_question(
        self,
        session: DiagnosisSession,
        differential: DifferentialDiagnosis,
    ) -> dict:
        """
        Generate question that best discriminates between top hypotheses.

        Uses PrimeKG to find phenotypes that:
        - Are present in hypothesis A but not B
        - Have high information content (IC)
        - Are clinically observable
        """
        top_two = differential.hypotheses[:2]
        if len(top_two) < 2:
            return {"question": "Can you describe any additional symptoms?", "type": "open"}

        # Find discriminating phenotypes via PrimeKG
        discriminating = await self.engine.primekg.execute(
            context=self.engine._create_context(),
            input_data={
                "operation": "find_discriminating_phenotypes",
                "disease_a": top_two[0].disease_id,
                "disease_b": top_two[1].disease_id,
                "already_present": session.phenotypes,
            }
        )

        if discriminating.data.get("phenotypes"):
            phenotype = discriminating.data["phenotypes"][0]
            return {
                "question": f"Do you experience {phenotype['description']}?",
                "type": "boolean",
                "hpo_id": phenotype["hpo_id"],
                "discriminates_for": top_two[0].disease_id,
                "discriminates_against": top_two[1].disease_id,
            }

        return {
            "question": "Are there any other symptoms you haven't mentioned?",
            "type": "open",
        }
```

---

## 5. Medical History Data Model

### 5.1 FHIR-Aligned Patient Model

```python
# forge/models/medical_history.py

class MedicalHistoryCategory(str, Enum):
    CONDITION = "condition"
    PROCEDURE = "procedure"
    MEDICATION = "medication"
    ALLERGY = "allergy"
    IMMUNIZATION = "immunization"
    FAMILY_HISTORY = "family_history"
    SOCIAL_HISTORY = "social_history"
    LAB_RESULT = "lab_result"
    VITAL_SIGN = "vital_sign"
    IMAGING = "imaging"

class MedicalHistoryEntry(ForgeModel, TimestampMixin):
    """Single entry in medical history."""
    entry_id: str
    category: MedicalHistoryCategory

    # Clinical coding
    icd10_code: str | None = None
    snomed_code: str | None = None
    rxnorm_code: str | None = None
    loinc_code: str | None = None

    # Descriptive
    description: str
    onset_date: datetime | None = None
    resolution_date: datetime | None = None
    is_active: bool = True

    # PrimeKG mapping
    primekg_node_id: str | None = None
    hpo_ids: list[str] = []

    # Source
    source_system: str | None = None
    verified: bool = False

class FamilyMember(ForgeModel):
    """Family member for family history."""
    relationship: str  # mother, father, sibling, etc.
    conditions: list[MedicalHistoryEntry] = []
    age_at_onset: dict[str, int] = {}  # condition -> age
    is_deceased: bool = False
    age_at_death: int | None = None

class PatientMedicalHistory(ForgeModel, TimestampMixin):
    """Complete patient medical history."""
    patient_id: str  # Anonymized ID

    # Demographics (optional, anonymized)
    age_range: str | None = None  # "30-40", "50-60", etc.
    sex: str | None = None
    ethnicity: str | None = None

    # History categories
    conditions: list[MedicalHistoryEntry] = []
    procedures: list[MedicalHistoryEntry] = []
    medications: list[MedicalHistoryEntry] = []
    allergies: list[MedicalHistoryEntry] = []
    immunizations: list[MedicalHistoryEntry] = []
    family_history: list[FamilyMember] = []
    social_history: dict = {}

    # Recent vitals and labs
    recent_vitals: list[MedicalHistoryEntry] = []
    recent_labs: list[MedicalHistoryEntry] = []

    # PrimeKG enrichment
    enriched_with_primekg: bool = False
    primekg_disease_associations: list[str] = []
    primekg_drug_interactions: list[str] = []
```

### 5.2 History Import Service

```python
# forge/services/medical_history_import.py

class MedicalHistoryImportService:
    """
    Import and normalize medical history from various formats.

    Supports:
    - FHIR R4 bundles
    - HL7 v2 messages
    - CCD/C-CDA documents
    - Custom CSV/JSON formats
    """

    async def import_fhir_bundle(
        self,
        bundle: dict,
        patient_id: str,
    ) -> PatientMedicalHistory:
        """Import from FHIR R4 bundle."""
        ...

    async def enrich_with_primekg(
        self,
        history: PatientMedicalHistory,
    ) -> PatientMedicalHistory:
        """Map conditions/medications to PrimeKG nodes."""

        for condition in history.conditions:
            # Map ICD-10 to MONDO via PrimeKG
            if condition.icd10_code:
                primekg_match = await self._map_icd10_to_mondo(condition.icd10_code)
                if primekg_match:
                    condition.primekg_node_id = primekg_match["mondo_id"]
                    condition.hpo_ids = primekg_match.get("associated_phenotypes", [])

        for medication in history.medications:
            # Map RxNorm to DrugBank via PrimeKG
            if medication.rxnorm_code:
                primekg_match = await self._map_rxnorm_to_drugbank(medication.rxnorm_code)
                if primekg_match:
                    medication.primekg_node_id = primekg_match["drugbank_id"]

        # Check for drug-disease interactions
        history.primekg_drug_interactions = await self._check_drug_interactions(history)

        history.enriched_with_primekg = True
        return history
```

---

## 6. HPO-Based Phenotype Pipeline

### 6.1 Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   HPO PHENOTYPE PIPELINE                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐                                               │
│  │  Raw Input   │ "patient has fatigue and joint pain"          │
│  └──────┬───────┘                                               │
│         │                                                       │
│         ▼                                                       │
│  ┌──────────────────────────────────────────┐                  │
│  │        CLINICAL NLP EXTRACTION           │                  │
│  │  • Named Entity Recognition (NER)        │                  │
│  │  • Negation Detection                    │                  │
│  │  • Temporal Extraction                   │                  │
│  └──────────────┬───────────────────────────┘                  │
│                 │                                               │
│                 ▼                                               │
│  ┌──────────────────────────────────────────┐                  │
│  │         HPO TERM MAPPING                  │                  │
│  │  • Exact match lookup                    │                  │
│  │  • Fuzzy matching (Levenshtein)          │                  │
│  │  • Semantic similarity (embeddings)      │                  │
│  │  • Synonym expansion                     │                  │
│  └──────────────┬───────────────────────────┘                  │
│                 │                                               │
│                 ▼                                               │
│  ┌──────────────────────────────────────────┐                  │
│  │         HPO HIERARCHY PROPAGATION         │                  │
│  │  • Ancestor term inclusion               │                  │
│  │  • IC (Information Content) calculation  │                  │
│  │  • Specificity scoring                   │                  │
│  └──────────────┬───────────────────────────┘                  │
│                 │                                               │
│                 ▼                                               │
│  ┌──────────────────────────────────────────┐                  │
│  │      NORMALIZED PHENOTYPE OUTPUT          │                  │
│  │  [HP:0001945, HP:0002829, HP:0000969]    │                  │
│  │  Fatigue    Joint pain   Bruising        │                  │
│  └──────────────────────────────────────────┘                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 HPO Service Implementation

```python
# forge/services/hpo_pipeline.py

class HPOPhenotypePipeline:
    """
    Pipeline for extracting and normalizing phenotypes to HPO terms.

    Uses the Human Phenotype Ontology (HPO) with 17,000+ terms
    organized in a directed acyclic graph (DAG).
    """

    def __init__(
        self,
        hpo_graph: nx.DiGraph,  # HPO hierarchy
        term_embeddings: dict[str, list[float]],  # HPO term embeddings
        llm_service: LLMService,
    ):
        self.hpo = hpo_graph
        self.embeddings = term_embeddings
        self.llm = llm_service

        # Build lookup structures
        self._name_to_id = {}
        self._synonym_to_id = {}
        self._build_lookup_tables()

    async def extract_and_normalize(
        self,
        symptoms: list[str],
        clinical_notes: str | None = None,
    ) -> list[HPOTerm]:
        """
        Extract phenotypes from symptoms and normalize to HPO.

        Returns list of HPO terms with confidence scores.
        """
        phenotypes = []

        # Process explicit symptoms
        for symptom in symptoms:
            matches = await self._match_to_hpo(symptom)
            phenotypes.extend(matches)

        # Extract from clinical notes via NLP
        if clinical_notes:
            extracted = await self._extract_from_notes(clinical_notes)
            phenotypes.extend(extracted)

        # Deduplicate and merge
        merged = self._merge_phenotypes(phenotypes)

        # Add ancestor terms for completeness
        with_ancestors = self._propagate_ancestors(merged)

        # Calculate information content
        for p in with_ancestors:
            p.information_content = self._calculate_ic(p.hpo_id)

        return with_ancestors

    async def _match_to_hpo(self, symptom: str) -> list[HPOTerm]:
        """Match symptom text to HPO terms."""
        normalized = symptom.lower().strip()

        # 1. Exact name match
        if normalized in self._name_to_id:
            return [HPOTerm(
                hpo_id=self._name_to_id[normalized],
                name=symptom,
                confidence=1.0,
                match_type="exact",
            )]

        # 2. Synonym match
        if normalized in self._synonym_to_id:
            return [HPOTerm(
                hpo_id=self._synonym_to_id[normalized],
                name=symptom,
                confidence=0.95,
                match_type="synonym",
            )]

        # 3. Fuzzy match (Levenshtein distance)
        fuzzy_matches = self._fuzzy_match(normalized, threshold=0.85)
        if fuzzy_matches:
            return [HPOTerm(
                hpo_id=m["hpo_id"],
                name=symptom,
                confidence=m["score"],
                match_type="fuzzy",
            ) for m in fuzzy_matches[:3]]

        # 4. Semantic similarity via embeddings
        symptom_embedding = await self._embed_text(symptom)
        semantic_matches = self._semantic_match(symptom_embedding, threshold=0.8)
        if semantic_matches:
            return [HPOTerm(
                hpo_id=m["hpo_id"],
                name=symptom,
                confidence=m["score"],
                match_type="semantic",
            ) for m in semantic_matches[:3]]

        # 5. LLM-assisted mapping (fallback)
        llm_match = await self._llm_map_to_hpo(symptom)
        if llm_match:
            return [HPOTerm(
                hpo_id=llm_match["hpo_id"],
                name=symptom,
                confidence=0.7,
                match_type="llm",
            )]

        return []

    def _calculate_ic(self, hpo_id: str) -> float:
        """
        Calculate Information Content for HPO term.

        IC = -log2(p(term)) where p(term) is frequency of term annotations.
        Higher IC = more specific/informative term.
        """
        # Use pre-computed IC from HPO annotation frequencies
        return self._ic_lookup.get(hpo_id, 0.0)

    async def calculate_phenotype_similarity(
        self,
        phenotypes_a: list[str],
        phenotypes_b: list[str],
    ) -> float:
        """
        Calculate semantic similarity between two phenotype sets.

        Uses Resnik similarity with IC-weighted Jaccard.
        """
        ic_a = sum(self._calculate_ic(p) for p in phenotypes_a)
        ic_b = sum(self._calculate_ic(p) for p in phenotypes_b)

        # Find most informative common ancestor for each pair
        similarity_sum = 0.0
        for pa in phenotypes_a:
            max_sim = 0.0
            for pb in phenotypes_b:
                mica = self._find_mica(pa, pb)  # Most Informative Common Ancestor
                mica_ic = self._calculate_ic(mica) if mica else 0.0
                sim = (2 * mica_ic) / (self._calculate_ic(pa) + self._calculate_ic(pb))
                max_sim = max(max_sim, sim)
            similarity_sum += max_sim

        return similarity_sum / len(phenotypes_a) if phenotypes_a else 0.0
```

---

## 7. Genetic Data Handling

### 7.1 Genetic Data Model

```python
# forge/models/genetic.py

class VariantClassification(str, Enum):
    PATHOGENIC = "pathogenic"
    LIKELY_PATHOGENIC = "likely_pathogenic"
    VUS = "vus"  # Variant of Uncertain Significance
    LIKELY_BENIGN = "likely_benign"
    BENIGN = "benign"

class GeneticVariant(ForgeModel):
    """Single genetic variant."""
    variant_id: str  # e.g., "rs123456" or "chr1:12345:A>G"
    gene_symbol: str
    entrez_gene_id: str | None = None

    # Variant details
    chromosome: str
    position: int
    reference: str
    alternate: str

    # Classification
    classification: VariantClassification
    classification_source: str  # ClinVar, Lab, etc.

    # Zygosity
    zygosity: str  # "heterozygous", "homozygous", "hemizygous"

    # Annotations
    hgvs_c: str | None = None  # cDNA notation
    hgvs_p: str | None = None  # Protein notation
    consequence: str | None = None  # missense, frameshift, etc.

    # PrimeKG linkage
    primekg_gene_node: str | None = None
    associated_diseases: list[str] = []  # MONDO IDs

class GeneticProfile(ForgeModel, TimestampMixin):
    """Patient genetic profile."""
    profile_id: str
    patient_id: str

    # Test information
    test_type: str  # WES, WGS, Panel, etc.
    test_date: datetime | None = None
    lab_name: str | None = None

    # Variants
    variants: list[GeneticVariant] = []

    # Summary
    pathogenic_count: int = 0
    vus_count: int = 0

    # PrimeKG enrichment
    gene_disease_associations: list[dict] = []
```

### 7.2 Genetic Data Handler

```python
# forge/services/genetic_handler.py

class GeneticDataHandler:
    """
    Handles genetic data integration with PrimeKG.

    Maps genetic variants to disease associations via
    PrimeKG gene-disease edges.
    """

    def __init__(self, primekg_overlay: PrimeKGOverlay):
        self.primekg = primekg_overlay

    async def process_vcf(
        self,
        vcf_content: str,
        filter_pathogenic: bool = True,
    ) -> GeneticProfile:
        """Process VCF file and extract clinically relevant variants."""
        ...

    async def enrich_with_primekg(
        self,
        profile: GeneticProfile,
    ) -> GeneticProfile:
        """
        Enrich genetic profile with PrimeKG gene-disease associations.
        """
        gene_ids = [v.entrez_gene_id for v in profile.variants if v.entrez_gene_id]

        for variant in profile.variants:
            if not variant.entrez_gene_id:
                continue

            # Query PrimeKG for gene-disease associations
            result = await self.primekg.execute(
                context=self._create_context(),
                input_data={
                    "operation": "gene_disease_association",
                    "gene_id": variant.entrez_gene_id,
                }
            )

            if result.success and result.data.get("associations"):
                variant.primekg_gene_node = result.data["gene_node"]
                variant.associated_diseases = [
                    a["disease_id"] for a in result.data["associations"]
                ]

                profile.gene_disease_associations.extend(result.data["associations"])

        return profile

    async def find_disease_candidates(
        self,
        profile: GeneticProfile,
        phenotypes: list[str],
    ) -> list[dict]:
        """
        Find disease candidates supported by both genetic and phenotypic evidence.
        """
        # Get diseases associated with pathogenic variants
        genetic_diseases = set()
        for variant in profile.variants:
            if variant.classification in [
                VariantClassification.PATHOGENIC,
                VariantClassification.LIKELY_PATHOGENIC
            ]:
                genetic_diseases.update(variant.associated_diseases)

        # Get diseases associated with phenotypes
        phenotype_result = await self.primekg.execute(
            context=self._create_context(),
            input_data={
                "operation": "phenotype_to_disease",
                "phenotypes": phenotypes,
            }
        )
        phenotype_diseases = {
            r["disease_id"] for r in phenotype_result.data.get("results", [])
        }

        # Intersection = highest confidence candidates
        overlap = genetic_diseases & phenotype_diseases

        # Score candidates
        candidates = []
        for disease_id in overlap:
            candidate = {
                "disease_id": disease_id,
                "genetic_support": True,
                "phenotype_support": True,
                "supporting_genes": [
                    v.gene_symbol for v in profile.variants
                    if disease_id in v.associated_diseases
                ],
                "supporting_phenotypes": [
                    p for p in phenotypes
                    # ... match logic
                ],
            }
            candidates.append(candidate)

        return sorted(candidates, key=lambda c: len(c["supporting_genes"]), reverse=True)
```

---

## 8. Multi-Agent Diagnostic System

### 8.1 Agent Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                MULTI-AGENT DIAGNOSTIC SYSTEM                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                 ORCHESTRATOR AGENT                        │   │
│  │  • Coordinates diagnostic workflow                        │   │
│  │  • Manages agent communication                            │   │
│  │  • Synthesizes final diagnosis                            │   │
│  └──────────────────────────────────────────────────────────┘   │
│                            │                                     │
│         ┌──────────────────┼──────────────────┐                 │
│         │                  │                  │                 │
│         ▼                  ▼                  ▼                 │
│  ┌────────────┐    ┌────────────┐    ┌────────────┐            │
│  │ PHENOTYPE  │    │  GENETIC   │    │ TREATMENT  │            │
│  │   AGENT    │    │   AGENT    │    │   AGENT    │            │
│  │            │    │            │    │            │            │
│  │ • HPO      │    │ • VCF      │    │ • Drug     │            │
│  │   mapping  │    │   parsing  │    │   lookup   │            │
│  │ • Disease  │    │ • Gene-    │    │ • Contra-  │            │
│  │   ranking  │    │   disease  │    │   indicate │            │
│  └────────────┘    └────────────┘    └────────────┘            │
│         │                  │                  │                 │
│         └──────────────────┴──────────────────┘                 │
│                            │                                     │
│                            ▼                                     │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                  EVIDENCE SYNTHESIS                       │   │
│  │  • Combine agent findings                                 │   │
│  │  • Resolve conflicts                                      │   │
│  │  • Build evidence chains (Isnad)                          │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 8.2 Agent Implementations

```python
# forge/agents/diagnostic_agents.py

class DiagnosticAgent(ABC):
    """Base class for diagnostic agents."""

    @abstractmethod
    async def analyze(self, context: DiagnosticContext) -> AgentResult:
        """Perform agent-specific analysis."""
        pass

    @abstractmethod
    async def get_evidence(self, hypothesis: str) -> list[Evidence]:
        """Get evidence supporting/refuting a hypothesis."""
        pass

class PhenotypeAgent(DiagnosticAgent):
    """Agent specialized in phenotype analysis."""

    def __init__(self, hpo_pipeline: HPOPhenotypePipeline, primekg: PrimeKGOverlay):
        self.hpo = hpo_pipeline
        self.primekg = primekg

    async def analyze(self, context: DiagnosticContext) -> AgentResult:
        """
        Analyze phenotypes and generate disease candidates.
        """
        # Normalize to HPO
        hpo_terms = await self.hpo.extract_and_normalize(
            context.symptoms,
            context.clinical_notes
        )

        # Query PrimeKG for disease matches
        matches = await self.primekg.execute(
            context=self._create_overlay_context(),
            input_data={
                "operation": "phenotype_to_disease",
                "phenotypes": [t.hpo_id for t in hpo_terms]
            }
        )

        return AgentResult(
            agent_name="phenotype",
            findings=matches.data.get("results", []),
            confidence=self._calculate_confidence(hpo_terms, matches),
            evidence_chain=[
                Evidence(
                    type=EvidenceType.PHENOTYPE_MATCH,
                    source=t.hpo_id,
                    description=f"Phenotype {t.name} maps to HPO:{t.hpo_id}",
                    weight=t.information_content,
                )
                for t in hpo_terms
            ]
        )

class GeneticAgent(DiagnosticAgent):
    """Agent specialized in genetic analysis."""

    def __init__(self, genetic_handler: GeneticDataHandler):
        self.handler = genetic_handler

    async def analyze(self, context: DiagnosticContext) -> AgentResult:
        """
        Analyze genetic data and find disease associations.
        """
        if not context.genetic_profile:
            return AgentResult(
                agent_name="genetic",
                findings=[],
                confidence=0.0,
                note="No genetic data provided"
            )

        # Enrich with PrimeKG
        enriched = await self.handler.enrich_with_primekg(context.genetic_profile)

        # Find candidates
        candidates = await self.handler.find_disease_candidates(
            enriched,
            [t.hpo_id for t in context.phenotypes]
        )

        return AgentResult(
            agent_name="genetic",
            findings=candidates,
            confidence=self._calculate_confidence(enriched),
            evidence_chain=[
                Evidence(
                    type=EvidenceType.GENE_ASSOCIATION,
                    source=v.gene_symbol,
                    description=f"{v.gene_symbol} variant ({v.classification.value})",
                    weight=self._variant_weight(v),
                )
                for v in enriched.variants
                if v.classification in [
                    VariantClassification.PATHOGENIC,
                    VariantClassification.LIKELY_PATHOGENIC
                ]
            ]
        )

class TreatmentAgent(DiagnosticAgent):
    """Agent specialized in treatment pathway analysis."""

    async def analyze(self, context: DiagnosticContext) -> AgentResult:
        """
        Analyze treatment implications for diagnosis candidates.
        """
        # Check for contraindications with current medications
        # Suggest treatment pathways
        # Identify drug-disease interactions
        ...

class OrchestratorAgent:
    """
    Coordinates multi-agent diagnostic workflow.
    """

    def __init__(
        self,
        phenotype_agent: PhenotypeAgent,
        genetic_agent: GeneticAgent,
        treatment_agent: TreatmentAgent,
        llm_service: LLMService,
    ):
        self.agents = {
            "phenotype": phenotype_agent,
            "genetic": genetic_agent,
            "treatment": treatment_agent,
        }
        self.llm = llm_service

    async def run_diagnostic_workflow(
        self,
        context: DiagnosticContext,
    ) -> DiagnosticWorkflowResult:
        """
        Run full multi-agent diagnostic workflow.
        """
        # Phase 1: Parallel agent analysis
        results = await asyncio.gather(
            self.agents["phenotype"].analyze(context),
            self.agents["genetic"].analyze(context),
            self.agents["treatment"].analyze(context),
        )

        # Phase 2: Evidence synthesis
        synthesized = await self._synthesize_evidence(results)

        # Phase 3: Conflict resolution
        resolved = await self._resolve_conflicts(synthesized)

        # Phase 4: Final ranking
        final_differential = self._rank_hypotheses(resolved)

        return DiagnosticWorkflowResult(
            agent_results={r.agent_name: r for r in results},
            synthesized_evidence=synthesized,
            final_differential=final_differential,
        )

    async def _synthesize_evidence(
        self,
        agent_results: list[AgentResult],
    ) -> SynthesizedEvidence:
        """
        Combine evidence from multiple agents.
        """
        # Find diseases mentioned by multiple agents
        disease_mentions = defaultdict(list)
        for result in agent_results:
            for finding in result.findings:
                disease_id = finding.get("disease_id")
                if disease_id:
                    disease_mentions[disease_id].append({
                        "agent": result.agent_name,
                        "confidence": result.confidence,
                        "evidence": finding,
                    })

        # Score by multi-agent agreement
        scored = []
        for disease_id, mentions in disease_mentions.items():
            score = sum(m["confidence"] for m in mentions) / len(self.agents)
            agent_agreement = len(mentions) / len(self.agents)

            scored.append({
                "disease_id": disease_id,
                "multi_agent_score": score * agent_agreement,
                "agents_supporting": [m["agent"] for m in mentions],
                "evidence": [m["evidence"] for m in mentions],
            })

        return SynthesizedEvidence(
            diseases=sorted(scored, key=lambda x: x["multi_agent_score"], reverse=True)
        )
```

---

## 9. Wearable Data Conversion

### 9.1 Supported Wearable Platforms

| Platform | Data Types | API |
|----------|-----------|-----|
| Apple HealthKit | Heart rate, HRV, sleep, activity | HealthKit API |
| Fitbit | Heart rate, sleep, steps, SpO2 | Web API |
| Garmin | Heart rate, HRV, sleep, stress | Connect API |
| Samsung Health | Heart rate, sleep, steps, stress | SDK |
| Oura Ring | Sleep, HRV, readiness, temperature | API |
| Whoop | Strain, recovery, sleep, HRV | API |

### 9.2 Wearable Data Models

```python
# forge/models/wearable.py

class WearableDataType(str, Enum):
    HEART_RATE = "heart_rate"
    HEART_RATE_VARIABILITY = "hrv"
    BLOOD_OXYGEN = "spo2"
    SLEEP = "sleep"
    ACTIVITY = "activity"
    TEMPERATURE = "temperature"
    RESPIRATORY_RATE = "respiratory_rate"
    BLOOD_PRESSURE = "blood_pressure"
    BLOOD_GLUCOSE = "blood_glucose"

class WearableMeasurement(ForgeModel):
    """Single wearable measurement."""
    timestamp: datetime
    data_type: WearableDataType
    value: float
    unit: str
    source_device: str

    # Quality indicators
    confidence: float = 1.0
    is_resting: bool | None = None

class WearableDataSummary(ForgeModel):
    """Aggregated wearable data for a time period."""
    period_start: datetime
    period_end: datetime

    # Heart metrics
    avg_heart_rate: float | None = None
    resting_heart_rate: float | None = None
    max_heart_rate: float | None = None
    hrv_rmssd: float | None = None
    hrv_sdnn: float | None = None

    # Sleep metrics
    total_sleep_hours: float | None = None
    deep_sleep_hours: float | None = None
    rem_sleep_hours: float | None = None
    sleep_efficiency: float | None = None

    # Activity metrics
    steps: int | None = None
    active_minutes: int | None = None
    calories_burned: int | None = None

    # Respiratory/oxygenation
    avg_spo2: float | None = None
    avg_respiratory_rate: float | None = None

    # Derived phenotypes (HPO)
    derived_phenotypes: list[str] = []

class WearablePhenotypeMapping(ForgeModel):
    """Rules for deriving phenotypes from wearable data."""
    metric: str
    condition: str  # "above", "below", "between"
    threshold: float | tuple[float, float]
    hpo_id: str
    hpo_name: str
    confidence: float
```

### 9.3 Wearable Data Converter

```python
# forge/services/wearable_converter.py

class WearableDataConverter:
    """
    Converts wearable device data into clinical phenotypes.

    Maps physiological measurements to HPO terms for
    integration with the diagnosis engine.
    """

    # Phenotype derivation rules
    PHENOTYPE_RULES = [
        # Cardiovascular
        WearablePhenotypeMapping(
            metric="resting_heart_rate",
            condition="above",
            threshold=100,
            hpo_id="HP:0001649",
            hpo_name="Tachycardia",
            confidence=0.8,
        ),
        WearablePhenotypeMapping(
            metric="resting_heart_rate",
            condition="below",
            threshold=60,
            hpo_id="HP:0001662",
            hpo_name="Bradycardia",
            confidence=0.7,
        ),
        WearablePhenotypeMapping(
            metric="avg_spo2",
            condition="below",
            threshold=94,
            hpo_id="HP:0012418",
            hpo_name="Hypoxemia",
            confidence=0.85,
        ),

        # Sleep
        WearablePhenotypeMapping(
            metric="sleep_efficiency",
            condition="below",
            threshold=0.75,
            hpo_id="HP:0002360",
            hpo_name="Sleep disturbance",
            confidence=0.7,
        ),

        # Add more rules...
    ]

    async def convert_to_phenotypes(
        self,
        summary: WearableDataSummary,
        lookback_days: int = 7,
    ) -> list[DerivedPhenotype]:
        """
        Derive clinical phenotypes from wearable data summary.

        Uses rule-based mapping with configurable thresholds
        and confidence scores.
        """
        derived = []

        for rule in self.PHENOTYPE_RULES:
            value = getattr(summary, rule.metric, None)
            if value is None:
                continue

            triggered = False
            if rule.condition == "above" and value > rule.threshold:
                triggered = True
            elif rule.condition == "below" and value < rule.threshold:
                triggered = True
            elif rule.condition == "between":
                low, high = rule.threshold
                triggered = low <= value <= high

            if triggered:
                derived.append(DerivedPhenotype(
                    hpo_id=rule.hpo_id,
                    hpo_name=rule.hpo_name,
                    source="wearable",
                    source_metric=rule.metric,
                    source_value=value,
                    confidence=rule.confidence,
                    derivation_rule=f"{rule.metric} {rule.condition} {rule.threshold}",
                ))

        summary.derived_phenotypes = [d.hpo_id for d in derived]
        return derived

    async def import_from_healthkit(
        self,
        healthkit_export: dict,
    ) -> WearableDataSummary:
        """Import from Apple HealthKit export."""
        ...

    async def import_from_fitbit(
        self,
        fitbit_data: dict,
    ) -> WearableDataSummary:
        """Import from Fitbit API response."""
        ...
```

---

## 10. Compliance Framework Alignment

### 10.1 HIPAA Controls

| HIPAA Requirement | Forge Implementation |
|-------------------|---------------------|
| Access Control (§164.312(a)(1)) | Capability-based permissions, TrustLevel enforcement |
| Audit Logs (§164.312(b)) | Immutable audit chain with SHA-256 hashes |
| Integrity (§164.312(c)(1)) | Capsule content hashes, Merkle tree lineage |
| Encryption (§164.312(e)(1)) | AES-256-GCM at rest, TLS 1.3 in transit |
| PHI De-identification | Patient ID anonymization, age ranges |

### 10.2 AI Governance (EU AI Act)

```python
# forge/compliance/ai_governance/diagnosis_ai.py

class DiagnosisAIGovernance:
    """
    EU AI Act compliance for diagnosis hypothesis engine.

    Classification: HIGH-RISK AI SYSTEM (Healthcare)
    """

    async def register_system(self):
        """Register diagnosis engine as high-risk AI system."""
        return await self.compliance_engine.register_ai_system({
            "system_name": "Forge Diagnosis Hypothesis Engine",
            "system_version": "1.0.0",
            "provider": "Forge",
            "risk_classification": "high_risk",
            "intended_purpose": "Clinical decision support for differential diagnosis",
            "use_cases": ["phenotype_analysis", "genetic_correlation", "drug_interaction"],
            "model_type": "Knowledge Graph + LLM Hybrid",
            "human_oversight_measures": [
                "physician_review_required",
                "confidence_thresholds",
                "override_capability",
            ],
        })

    async def log_diagnosis_decision(
        self,
        session_id: str,
        differential: DifferentialDiagnosis,
    ):
        """Log diagnosis decision with explainability."""
        for hypothesis in differential.hypotheses:
            await self.compliance_engine.log_ai_decision({
                "ai_system_id": "diagnosis_engine_v1",
                "decision_type": "diagnostic_hypothesis",
                "decision_outcome": hypothesis.disease_name,
                "confidence_score": hypothesis.probability_score,
                "reasoning_chain": [
                    e.description for e in hypothesis.supporting_evidence
                ],
                "key_factors": [
                    {
                        "factor": "phenotype_overlap",
                        "value": hypothesis.phenotype_overlap_score,
                        "weight": 0.4,
                    },
                    {
                        "factor": "gene_support",
                        "value": hypothesis.gene_support_score,
                        "weight": 0.3,
                    },
                ],
                "has_legal_effect": False,  # Advisory only
                "human_review_required": True,
            })
```

### 10.3 Data Residency

```python
# Ensure medical data stays in compliant regions
MEDICAL_DATA_RESIDENCY = {
    "patient_data": DataRegion.US_EAST,  # HIPAA compliant
    "eu_patient_data": DataRegion.EU_WEST,  # GDPR compliant
    "primekg_data": DataRegion.US_EAST,  # Public research data
}
```

---

## 11. Implementation Roadmap

### Phase 1: Foundation (Weeks 1-2)
- [ ] Set up PrimeKG data import pipeline
- [ ] Create Neo4j schema extensions
- [ ] Implement basic PrimeKG overlay
- [ ] Add phenotype-to-disease query

### Phase 2: HPO Pipeline (Weeks 3-4)
- [ ] Build HPO hierarchy loader
- [ ] Implement NER for symptom extraction
- [ ] Add HPO term matching (exact, fuzzy, semantic)
- [ ] Create IC calculation service

### Phase 3: Genetic Integration (Weeks 5-6)
- [ ] VCF parsing service
- [ ] Gene-disease association queries
- [ ] Genetic profile enrichment
- [ ] Combined phenotype-genetic scoring

### Phase 4: Hypothesis Engine (Weeks 7-8)
- [ ] Bayesian probability model
- [ ] Evidence chain construction
- [ ] Hypothesis ranking algorithm
- [ ] Confirmatory test suggestions

### Phase 5: Autonomous Flow (Weeks 9-10)
- [ ] Session state machine
- [ ] Discriminating question generator
- [ ] Interrupt/resume functionality
- [ ] Confidence threshold tuning

### Phase 6: Multi-Agent System (Weeks 11-12)
- [ ] Agent base classes
- [ ] Phenotype, Genetic, Treatment agents
- [ ] Orchestrator agent
- [ ] Evidence synthesis logic

### Phase 7: Wearable Integration (Week 13)
- [ ] Wearable data models
- [ ] Platform-specific importers
- [ ] Phenotype derivation rules
- [ ] Real-time data streaming

### Phase 8: Compliance & Testing (Weeks 14-16)
- [ ] HIPAA audit logging
- [ ] EU AI Act registration
- [ ] Integration tests
- [ ] Clinical validation studies
- [ ] Documentation

---

## Appendix A: PrimeKG Node/Edge Reference

### A.1 Node Types
1. Drug
2. Disease
3. Anatomy
4. Pathway
5. Gene/Protein
6. Biological Process
7. Molecular Function
8. Cellular Component
9. Effect/Phenotype
10. Exposure

### A.2 Key Edge Types
- `indication` - Drug treats disease
- `contraindication` - Drug contraindicated for disease
- `off_label_use` - Drug used off-label for disease
- `disease_phenotype` - Disease manifests phenotype
- `drug_target` - Drug targets gene/protein
- `gene_disease` - Gene associated with disease
- `pathway_gene` - Gene participates in pathway
- `exposure_disease` - Exposure linked to disease

---

## Appendix B: HPO Integration Details

### B.1 HPO Statistics
- 17,000+ phenotype terms
- Directed Acyclic Graph (DAG) structure
- 5 main branches: Phenotypic abnormality, Clinical modifier, Mode of inheritance, Past medical history, Blood group

### B.2 Disease-Phenotype Sources
- OMIM (Mendelian diseases)
- Orphanet (Rare diseases)
- DECIPHER (Developmental disorders)
- Monarch Initiative (Cross-species)

---

## References

1. Chandak, P., Huang, K., & Zitnik, M. (2023). Building a knowledge graph to enable precision medicine. *Scientific Data*.
2. Human Phenotype Ontology: https://hpo.jax.org/
3. PrimeKG Repository: https://github.com/mims-harvard/PrimeKG
4. Forge V3 Compliance Framework Documentation
5. EU AI Act Requirements for High-Risk AI Systems
