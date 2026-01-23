# PrimeKG Differential Diagnosis Engine - Implementation Plan

**Total Tasks:** 127 tasks across 8 phases
**Estimated Duration:** 16 weeks

---

## Phase 1: PrimeKG Data Foundation (Weeks 1-2)

### 1.1 Data Infrastructure
- [ ] **1.1.1** Create `forge/services/primekg/` directory structure
- [ ] **1.1.2** Implement PrimeKG data download script from Harvard Dataverse
- [ ] **1.1.3** Create CSV parser for nodes.csv (129,375 nodes)
- [ ] **1.1.4** Create CSV parser for edges.csv (4,050,249 edges)
- [ ] **1.1.5** Build data validation and integrity checks
- [ ] **1.1.6** Create progress tracking for large imports

### 1.2 Neo4j Schema Extensions
- [ ] **1.2.1** Create `forge/database/primekg_schema.py`
- [ ] **1.2.2** Define PrimeKGDisease node label and constraints
- [ ] **1.2.3** Define PrimeKGGene node label and constraints
- [ ] **1.2.4** Define PrimeKGDrug node label and constraints
- [ ] **1.2.5** Define PrimeKGPhenotype node label and constraints
- [ ] **1.2.6** Define PrimeKGAnatomy node label and constraints
- [ ] **1.2.7** Define PrimeKGPathway node label and constraints
- [ ] **1.2.8** Define PrimeKGBioProcess node label and constraints
- [ ] **1.2.9** Define PrimeKGMolFunction node label and constraints
- [ ] **1.2.10** Define PrimeKGCellComponent node label and constraints
- [ ] **1.2.11** Define PrimeKGExposure node label and constraints
- [ ] **1.2.12** Create vector index for PrimeKG embeddings
- [ ] **1.2.13** Create full-text index for clinical descriptions
- [ ] **1.2.14** Create relationship type indexes for all 30 edge types

### 1.3 Import Service
- [ ] **1.3.1** Create `forge/services/primekg/import_service.py`
- [ ] **1.3.2** Implement batch node import (1000 nodes per batch)
- [ ] **1.3.3** Implement batch edge import (5000 edges per batch)
- [ ] **1.3.4** Add retry logic for failed batches
- [ ] **1.3.5** Implement import progress persistence (resume capability)
- [ ] **1.3.6** Create import validation report generator
- [ ] **1.3.7** Build import CLI command

### 1.4 Embedding Generation
- [ ] **1.4.1** Create `forge/services/primekg/embedding_service.py`
- [ ] **1.4.2** Implement clinical description embedding for diseases
- [ ] **1.4.3** Implement drug description embedding
- [ ] **1.4.4** Add batch embedding with rate limiting
- [ ] **1.4.5** Create embedding cache to avoid re-generation

---

## Phase 2: PrimeKG Overlay (Week 3)

### 2.1 Overlay Core
- [ ] **2.1.1** Create `forge/overlays/primekg_overlay.py`
- [ ] **2.1.2** Define NAME, VERSION, DESCRIPTION class attributes
- [ ] **2.1.3** Define SUBSCRIBED_EVENTS set
- [ ] **2.1.4** Define REQUIRED_CAPABILITIES set
- [ ] **2.1.5** Set MIN_TRUST_LEVEL to TRUSTED
- [ ] **2.1.6** Configure DEFAULT_FUEL_BUDGET (100MB, 60s timeout)
- [ ] **2.1.7** Implement __init__ with Neo4j client injection
- [ ] **2.1.8** Implement initialize() with HPO hierarchy preload
- [ ] **2.1.9** Implement cleanup() for resource release
- [ ] **2.1.10** Implement execute() router for operations

### 2.2 Query Operations
- [ ] **2.2.1** Implement `_phenotype_to_disease()` - HPO to MONDO mapping
- [ ] **2.2.2** Implement `_disease_to_drugs()` - indication/contraindication lookup
- [ ] **2.2.3** Implement `_gene_disease_association()` - gene-disease edges
- [ ] **2.2.4** Implement `_pathway_analysis()` - pathway traversal
- [ ] **2.2.5** Implement `_semantic_enrich()` - embedding-based search
- [ ] **2.2.6** Implement `_find_discriminating_phenotypes()` - for Q&A
- [ ] **2.2.7** Implement `_get_disease_details()` - full disease info
- [ ] **2.2.8** Implement `_check_drug_interactions()` - medication safety

### 2.3 Integration
- [ ] **2.3.1** Add PrimeKGOverlay to `forge/overlays/__init__.py`
- [ ] **2.3.2** Add to CORE_OVERLAY_CAPABILITIES in `models/overlay.py`
- [ ] **2.3.3** Create factory function `create_primekg_overlay()`
- [ ] **2.3.4** Register with OverlayManager in startup
- [ ] **2.3.5** Create API routes in `forge/api/routes/primekg.py`
- [ ] **2.3.6** Write unit tests for all operations
- [ ] **2.3.7** Write integration tests with real Neo4j

---

## Phase 3: HPO Phenotype Pipeline (Weeks 4-5)

### 3.1 HPO Data Loading
- [ ] **3.1.1** Create `forge/services/hpo/` directory
- [ ] **3.1.2** Download HPO ontology file (hp.obo or hp.json)
- [ ] **3.1.3** Parse HPO into NetworkX DAG
- [ ] **3.1.4** Build term name → HPO ID lookup
- [ ] **3.1.5** Build synonym → HPO ID lookup
- [ ] **3.1.6** Calculate Information Content (IC) for all terms
- [ ] **3.1.7** Cache HPO hierarchy in memory

### 3.2 HPO Term Matching
- [ ] **3.2.1** Create `forge/services/hpo/matcher.py`
- [ ] **3.2.2** Implement exact name matching
- [ ] **3.2.3** Implement synonym matching
- [ ] **3.2.4** Implement fuzzy matching (Levenshtein distance)
- [ ] **3.2.5** Implement semantic matching (embedding similarity)
- [ ] **3.2.6** Implement LLM-assisted mapping fallback
- [ ] **3.2.7** Create confidence scoring for each match type

### 3.3 Clinical NLP
- [ ] **3.3.1** Create `forge/services/hpo/nlp_extractor.py`
- [ ] **3.3.2** Implement symptom NER using spaCy/medspaCy
- [ ] **3.3.3** Implement negation detection (NegEx algorithm)
- [ ] **3.3.4** Implement temporal extraction (onset, duration)
- [ ] **3.3.5** Implement severity extraction
- [ ] **3.3.6** Create clinical note preprocessing

### 3.4 HPO Pipeline Service
- [ ] **3.4.1** Create `forge/services/hpo/pipeline.py`
- [ ] **3.4.2** Implement `extract_and_normalize()` main method
- [ ] **3.4.3** Implement ancestor propagation
- [ ] **3.4.4** Implement phenotype deduplication
- [ ] **3.4.5** Implement `calculate_phenotype_similarity()` (Resnik)
- [ ] **3.4.6** Implement `find_most_informative_ancestor()`
- [ ] **3.4.7** Write comprehensive unit tests

---

## Phase 4: Genetic Data Handling (Week 6)

### 4.1 Data Models
- [ ] **4.1.1** Create `forge/models/genetic.py`
- [ ] **4.1.2** Define VariantClassification enum
- [ ] **4.1.3** Define GeneticVariant model
- [ ] **4.1.4** Define GeneticProfile model
- [ ] **4.1.5** Define inheritance pattern enums

### 4.2 VCF Processing
- [ ] **4.2.1** Create `forge/services/genetic/vcf_parser.py`
- [ ] **4.2.2** Implement VCF file parsing
- [ ] **4.2.3** Extract variant annotations (HGVS, consequence)
- [ ] **4.2.4** Map variants to gene symbols
- [ ] **4.2.5** Filter by clinical significance
- [ ] **4.2.6** Handle multi-sample VCFs

### 4.3 Genetic Handler Service
- [ ] **4.3.1** Create `forge/services/genetic/handler.py`
- [ ] **4.3.2** Implement `process_vcf()` method
- [ ] **4.3.3** Implement `enrich_with_primekg()` - gene-disease mapping
- [ ] **4.3.4** Implement `find_disease_candidates()` - combined scoring
- [ ] **4.3.5** Implement inheritance pattern analysis
- [ ] **4.3.6** Create variant prioritization algorithm

---

## Phase 5: Diagnosis Engine Core (Weeks 7-8)

### 5.1 Data Models
- [ ] **5.1.1** Create `forge/models/diagnosis.py`
- [ ] **5.1.2** Define DiagnosisConfidence enum
- [ ] **5.1.3** Define EvidenceType enum
- [ ] **5.1.4** Define DiagnosticEvidence model
- [ ] **5.1.5** Define DiagnosticHypothesis model
- [ ] **5.1.6** Define DifferentialDiagnosis model
- [ ] **5.1.7** Define DiagnosisInput model

### 5.2 Hypothesis Engine
- [ ] **5.2.1** Create `forge/services/diagnosis/engine.py`
- [ ] **5.2.2** Implement `generate_differential()` main method
- [ ] **5.2.3** Implement Bayesian prior loading from epidemiology
- [ ] **5.2.4** Implement `_calculate_phenotype_likelihood()`
- [ ] **5.2.5** Implement `_bayesian_update()` posterior calculation
- [ ] **5.2.6** Implement `_build_evidence_chain()` (Isnad)
- [ ] **5.2.7** Implement `_suggest_confirmatory_tests()`
- [ ] **5.2.8** Implement `_rank_hypotheses()` by composite score
- [ ] **5.2.9** Implement `_score_to_confidence()` mapping

### 5.3 Evidence Chain Builder
- [ ] **5.3.1** Create `forge/services/diagnosis/evidence.py`
- [ ] **5.3.2** Implement evidence extraction from PrimeKG paths
- [ ] **5.3.3** Implement evidence weighting by type
- [ ] **5.3.4** Implement contradiction detection
- [ ] **5.3.5** Implement evidence summarization
- [ ] **5.3.6** Create evidence visualization data

---

## Phase 6: Autonomous Session Control (Weeks 9-10)

### 6.1 Session Models
- [ ] **6.1.1** Create `forge/models/diagnosis_session.py`
- [ ] **6.1.2** Define DiagnosisSessionState enum
- [ ] **6.1.3** Define DiagnosisSession model
- [ ] **6.1.4** Define DiagnosisSessionResponse model
- [ ] **6.1.5** Define Question model for Q&A

### 6.2 Session Store
- [ ] **6.2.1** Create `forge/services/diagnosis/session_store.py`
- [ ] **6.2.2** Implement Redis-backed session storage
- [ ] **6.2.3** Implement session TTL and expiration
- [ ] **6.2.4** Implement session recovery from persistence

### 6.3 Autonomous Controller
- [ ] **6.3.1** Create `forge/services/diagnosis/controller.py`
- [ ] **6.3.2** Implement `start_session()` method
- [ ] **6.3.3** Implement `process()` state machine
- [ ] **6.3.4** Implement `_handle_intake()` state
- [ ] **6.3.5** Implement `_handle_analyzing()` state
- [ ] **6.3.6** Implement `_handle_questioning()` state
- [ ] **6.3.7** Implement `_handle_refining()` state
- [ ] **6.3.8** Implement `interrupt()` method
- [ ] **6.3.9** Implement `resume()` method
- [ ] **6.3.10** Implement `_generate_discriminating_question()`
- [ ] **6.3.11** Implement `_process_answer()` method
- [ ] **6.3.12** Create confidence threshold tuning

### 6.4 API Endpoints
- [ ] **6.4.1** Create `forge/api/routes/diagnosis.py`
- [ ] **6.4.2** POST /diagnosis/sessions - start session
- [ ] **6.4.3** POST /diagnosis/sessions/{id}/process - continue
- [ ] **6.4.4** POST /diagnosis/sessions/{id}/answer - submit answer
- [ ] **6.4.5** POST /diagnosis/sessions/{id}/interrupt - pause
- [ ] **6.4.6** POST /diagnosis/sessions/{id}/resume - resume
- [ ] **6.4.7** GET /diagnosis/sessions/{id} - get status
- [ ] **6.4.8** GET /diagnosis/sessions/{id}/differential - get results

---

## Phase 7: Multi-Agent System (Weeks 11-12)

### 7.1 Agent Base
- [ ] **7.1.1** Create `forge/agents/` directory
- [ ] **7.1.2** Create `forge/agents/base.py` with DiagnosticAgent ABC
- [ ] **7.1.3** Define AgentResult model
- [ ] **7.1.4** Define DiagnosticContext model

### 7.2 Specialized Agents
- [ ] **7.2.1** Create `forge/agents/phenotype_agent.py`
- [ ] **7.2.2** Implement PhenotypeAgent.analyze()
- [ ] **7.2.3** Implement PhenotypeAgent.get_evidence()
- [ ] **7.2.4** Create `forge/agents/genetic_agent.py`
- [ ] **7.2.5** Implement GeneticAgent.analyze()
- [ ] **7.2.6** Implement GeneticAgent.get_evidence()
- [ ] **7.2.7** Create `forge/agents/treatment_agent.py`
- [ ] **7.2.8** Implement TreatmentAgent.analyze()
- [ ] **7.2.9** Implement TreatmentAgent.get_evidence()

### 7.3 Orchestrator
- [ ] **7.3.1** Create `forge/agents/orchestrator.py`
- [ ] **7.3.2** Implement `run_diagnostic_workflow()`
- [ ] **7.3.3** Implement parallel agent execution
- [ ] **7.3.4** Implement `_synthesize_evidence()`
- [ ] **7.3.5** Implement `_resolve_conflicts()`
- [ ] **7.3.6** Implement multi-agent agreement scoring
- [ ] **7.3.7** Create agent coordination logging

---

## Phase 8: Medical History & Wearables (Week 13)

### 8.1 Medical History Models
- [ ] **8.1.1** Create `forge/models/medical_history.py`
- [ ] **8.1.2** Define MedicalHistoryCategory enum
- [ ] **8.1.3** Define MedicalHistoryEntry model
- [ ] **8.1.4** Define FamilyMember model
- [ ] **8.1.5** Define PatientMedicalHistory model

### 8.2 History Import Service
- [ ] **8.2.1** Create `forge/services/medical_history/import_service.py`
- [ ] **8.2.2** Implement FHIR R4 bundle parser
- [ ] **8.2.3** Implement ICD-10 to MONDO mapping
- [ ] **8.2.4** Implement RxNorm to DrugBank mapping
- [ ] **8.2.5** Implement `enrich_with_primekg()` method
- [ ] **8.2.6** Implement drug interaction checker

### 8.3 Wearable Data Models
- [ ] **8.3.1** Create `forge/models/wearable.py`
- [ ] **8.3.2** Define WearableDataType enum
- [ ] **8.3.3** Define WearableMeasurement model
- [ ] **8.3.4** Define WearableDataSummary model
- [ ] **8.3.5** Define WearablePhenotypeMapping model

### 8.4 Wearable Converter
- [ ] **8.4.1** Create `forge/services/wearable/converter.py`
- [ ] **8.4.2** Define phenotype derivation rules
- [ ] **8.4.3** Implement `convert_to_phenotypes()` method
- [ ] **8.4.4** Implement Apple HealthKit importer
- [ ] **8.4.5** Implement Fitbit API importer
- [ ] **8.4.6** Implement Garmin Connect importer
- [ ] **8.4.7** Implement Oura Ring importer

---

## Phase 9: Compliance & Testing (Weeks 14-16)

### 9.1 HIPAA Compliance
- [ ] **9.1.1** Create `forge/compliance/hipaa/diagnosis_audit.py`
- [ ] **9.1.2** Implement PHI access logging
- [ ] **9.1.3** Implement patient ID anonymization
- [ ] **9.1.4** Implement minimum necessary access controls
- [ ] **9.1.5** Create audit report generator

### 9.2 EU AI Act Compliance
- [ ] **9.2.1** Create `forge/compliance/ai_governance/diagnosis_ai.py`
- [ ] **9.2.2** Implement high-risk AI system registration
- [ ] **9.2.3** Implement decision logging with explainability
- [ ] **9.2.4** Implement human oversight checkpoints
- [ ] **9.2.5** Create model documentation generator

### 9.3 Testing
- [ ] **9.3.1** Write unit tests for all services (target: 80% coverage)
- [ ] **9.3.2** Write integration tests for diagnosis workflow
- [ ] **9.3.3** Write E2E tests for complete session flow
- [ ] **9.3.4** Create performance benchmarks
- [ ] **9.3.5** Create load tests for concurrent sessions
- [ ] **9.3.6** Clinical validation test cases

### 9.4 Documentation
- [ ] **9.4.1** Write API documentation (OpenAPI/Swagger)
- [ ] **9.4.2** Write user guide for diagnosis engine
- [ ] **9.4.3** Write developer guide for extending agents
- [ ] **9.4.4** Create clinical workflow diagrams
- [ ] **9.4.5** Write deployment guide

---

## Task Summary by Phase

| Phase | Description | Tasks | Duration |
|-------|-------------|-------|----------|
| 1 | PrimeKG Data Foundation | 28 | 2 weeks |
| 2 | PrimeKG Overlay | 18 | 1 week |
| 3 | HPO Phenotype Pipeline | 21 | 2 weeks |
| 4 | Genetic Data Handling | 13 | 1 week |
| 5 | Diagnosis Engine Core | 17 | 2 weeks |
| 6 | Autonomous Session Control | 20 | 2 weeks |
| 7 | Multi-Agent System | 14 | 2 weeks |
| 8 | Medical History & Wearables | 16 | 1 week |
| 9 | Compliance & Testing | 15 | 3 weeks |
| **Total** | | **162** | **16 weeks** |

---

## Dependencies Graph

```
Phase 1 (PrimeKG Data) ─────┬─────► Phase 2 (PrimeKG Overlay)
                            │
                            └─────► Phase 3 (HPO Pipeline) ──┬──► Phase 5 (Engine)
                                                             │
Phase 4 (Genetic) ───────────────────────────────────────────┘
                                                             │
                                                             ▼
                                              Phase 6 (Autonomous Flow)
                                                             │
                                                             ▼
                                              Phase 7 (Multi-Agent)
                                                             │
Phase 8 (History/Wearables) ─────────────────────────────────┘
                                                             │
                                                             ▼
                                              Phase 9 (Compliance/Testing)
```

---

## Getting Started

To begin implementation, start with **Phase 1.1.1**:

```bash
mkdir -p forge-cascade-v2/forge/services/primekg
touch forge-cascade-v2/forge/services/primekg/__init__.py
touch forge-cascade-v2/forge/services/primekg/download.py
```

Then implement the data download script to fetch PrimeKG from Harvard Dataverse.
