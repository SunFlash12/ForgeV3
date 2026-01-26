"""
Seed Capsule Definitions for E2E Tests

Defines 11 capsules covering all CapsuleType values, 7 semantic edge types,
a 3-level lineage chain, and two tokenization candidates. Domain: Rare Disease
Genomics -- chosen because it naturally produces hierarchical knowledge,
contains both consensus and disagreement, and creates assets genuinely worth
tokenizing.
"""

from __future__ import annotations

from forge.models.base import CapsuleType
from forge.models.semantic_edges import (
    ContradictionSeverity,
    EvidenceType,
    SemanticRelationType,
)

# ═══════════════════════════════════════════════════════════════════════════════
# 11 SEED CAPSULES
# ═══════════════════════════════════════════════════════════════════════════════


def _capsule_defs() -> list[dict]:
    """Return raw capsule payloads (ready for ``CapsuleCreate``)."""

    return [
        # ── C1 KNOWLEDGE ─────────────────────────────────────────────
        {
            "title": "Rare Disease Genomic Ontology v2.0",
            "type": CapsuleType.KNOWLEDGE,
            "content": (
                "A structured ontology mapping 4,200+ rare diseases to their "
                "genomic variants, including pathogenic/likely-pathogenic "
                "classifications following ACMG/AMP guidelines. Covers autosomal "
                "dominant, autosomal recessive, X-linked, and mitochondrial "
                "inheritance patterns. Cross-references OMIM, OrphaNet, ClinVar, "
                "and HGMD databases. Version 2.0 adds structural variant "
                "annotations and pharmacogenomic markers for 340 conditions "
                "with known drug-gene interactions. Includes 1,280 curated "
                "gene-disease associations validated by clinical experts."
            ),
            "tags": ["genomics", "ontology", "rare-disease", "acmg", "clinvar"],
            "metadata": {"version": "2.0", "diseases_count": 4200},
        },
        # ── C2 INSIGHT ───────────────────────────────────────────────
        {
            "title": "Diagnostic Yield Analysis: WGS vs Panel",
            "type": CapsuleType.INSIGHT,
            "content": (
                "Whole-genome sequencing (WGS) achieved a 47% diagnostic yield "
                "across 2,100 undiagnosed rare-disease cases versus 28% for "
                "targeted gene panels. The 19-percentage-point uplift was driven "
                "by structural variants (SVs) missed by short-read panels and "
                "deep-intronic pathogenic variants unreachable by exome capture. "
                "Median turnaround time was 14 days (WGS) vs 9 days (panel). "
                "Cost-effectiveness analysis shows WGS dominates when per-case "
                "costs drop below USD 1,200 and re-analysis loops are avoided. "
                "Statistical significance confirmed (p < 0.001, Fisher exact)."
            ),
            "tags": ["genomics", "diagnostics", "analysis", "wgs", "rare-disease"],
            "metadata": {"sample_size": 2100, "diagnostic_yield_wgs": 0.47},
        },
        # ── C3 DECISION ──────────────────────────────────────────────
        {
            "title": "Adopt Ensemble Variant Classifier",
            "type": CapsuleType.DECISION,
            "content": (
                "Decision to adopt an ensemble machine-learning classifier for "
                "variant pathogenicity assessment, replacing manual ACMG rules. "
                "The ensemble combines CADD, REVEL, and SpliceAI scores through "
                "a random-forest meta-learner trained on ClinVar gold-standard "
                "variants. Rationale: reduces inter-analyst discordance from 12% "
                "to 3%, cuts median classification time from 22 min to 90 sec, "
                "and improves sensitivity on variants-of-uncertain-significance "
                "by 18%. Approved by the genomics steering committee on 2024-07-15."
            ),
            "tags": ["decision", "governance", "variant-calling", "ml", "genomics"],
            "metadata": {"approved_date": "2024-07-15", "committee": "genomics_steering"},
        },
        # ── C4 CODE ──────────────────────────────────────────────────
        {
            "title": "Ensemble Variant Classifier Implementation",
            "type": CapsuleType.CODE,
            "content": (
                "import numpy as np\n"
                "from sklearn.ensemble import RandomForestClassifier\n"
                "from sklearn.model_selection import cross_val_score\n\n"
                "class EnsembleVariantClassifier:\n"
                '    """Multi-model ensemble combining CADD, REVEL, and SpliceAI\n'
                "    scores with a random-forest meta-learner. Trained on ClinVar\n"
                "    gold-standard variants. Achieves 94.2% sensitivity, 97.8%\n"
                "    specificity on the held-out test set. Includes SHAP\n"
                '    explainability module for clinical interpretability."""\n\n'
                "    def __init__(self, n_estimators: int = 500):\n"
                "        self.model = RandomForestClassifier(\n"
                "            n_estimators=n_estimators,\n"
                "            max_depth=12,\n"
                "            class_weight='balanced',\n"
                "        )\n\n"
                "    def predict(self, features: np.ndarray) -> np.ndarray:\n"
                "        return self.model.predict(features)\n"
            ),
            "tags": ["code", "classifier", "python", "machine-learning", "variant-calling"],
            "metadata": {"language": "python", "framework": "scikit-learn", "accuracy": 0.961},
        },
        # ── C5 LESSON ────────────────────────────────────────────────
        {
            "title": "False Positive Rate in Structural Variant Calls",
            "type": CapsuleType.LESSON,
            "content": (
                "Lesson learned from production deployment: structural variant "
                "(SV) callers (Manta, DELLY2, LUMPY) produce a false-positive "
                "rate of 25-40% when applied to low-coverage WGS data (< 15x). "
                "Root cause is insufficient split-read evidence at breakpoints. "
                "Mitigation: require concordance from at least 2 of 3 callers "
                "and set a minimum of 5 supporting reads per breakpoint. Post-"
                "filter false-positive rate drops to 8%, preserving 92% of true "
                "positives. Lesson applies to all germline SV analyses on short-"
                "read platforms."
            ),
            "tags": ["lesson", "quality", "sv-calling", "genomics", "production"],
            "metadata": {"false_positive_before": 0.33, "false_positive_after": 0.08},
        },
        # ── C6 WARNING ───────────────────────────────────────────────
        {
            "title": "Diagnostic Yield Inflation from Batch Effects",
            "type": CapsuleType.WARNING,
            "content": (
                "Analysis reveals the 47% diagnostic yield reported in C2 is "
                "inflated by 8-12 percentage points due to batch effects in the "
                "sequencing cohort. When controlling for referral bias and "
                "sequencing platform differences, the true yield is 35-39%. "
                "Recommends re-analysis with proper cohort stratification before "
                "operational decisions. Specific confounders identified: 62% of "
                "cases were referrals from tertiary centres (higher pre-test "
                "probability), and Illumina NovaSeq batches had 15% higher call "
                "rates than HiSeq batches."
            ),
            "tags": ["warning", "quality", "batch-effects", "diagnostics", "genomics"],
            "metadata": {"corrected_yield_low": 0.35, "corrected_yield_high": 0.39},
        },
        # ── C7 PRINCIPLE ─────────────────────────────────────────────
        {
            "title": "Genomic Data Sovereignty Principle",
            "type": CapsuleType.PRINCIPLE,
            "content": (
                "Guiding principle: Genomic data generated within the Forge "
                "knowledge graph must respect data sovereignty requirements of "
                "the originating jurisdiction. Implementations must support: "
                "(1) geographic storage constraints (EU GDPR, AU Privacy Act), "
                "(2) consent-granularity controls allowing per-variant opt-out, "
                "(3) right-to-erasure workflows that propagate through lineage "
                "chains without breaking Merkle integrity, (4) federated query "
                "interfaces that return aggregate statistics without raw variant "
                "data crossing borders. This principle elaborates on C1 by "
                "constraining how the ontology may be queried."
            ),
            "tags": ["principle", "ethics", "data-governance", "privacy", "genomics"],
            "metadata": {"jurisdictions": ["EU", "AU", "US"]},
        },
        # ── C8 MEMORY ────────────────────────────────────────────────
        {
            "title": "Q3 2024 Variant Pipeline Retrospective",
            "type": CapsuleType.MEMORY,
            "content": (
                "Retrospective for Q3 2024 variant classification pipeline. "
                "Key outcomes: deployed ensemble classifier (C4), documented "
                "SV false-positive lesson (C5), and identified batch-effect "
                "warning (C6). Pipeline throughput increased 340% (from 50 to "
                "220 cases per week). Three P/LP reclassifications triggered "
                "clinical re-contacts. Incident: storage quota exceeded on "
                "2024-08-22 causing 4-hour downtime. Action item: implement "
                "automated storage monitoring. Next quarter goals: integrate "
                "PrimeKG for drug-repurposing overlays and complete data-"
                "sovereignty audit."
            ),
            "tags": ["memory", "retrospective", "pipeline", "q3-2024", "genomics"],
            "metadata": {"quarter": "Q3-2024", "throughput_increase_pct": 340},
        },
        # ── C9 CONFIG ────────────────────────────────────────────────
        {
            "title": "Production Classifier Thresholds",
            "type": CapsuleType.CONFIG,
            "content": (
                "Production configuration for the ensemble variant classifier "
                "(C4) and SV post-filtering (C5). Thresholds:\n"
                "  cadd_phred_min: 20\n"
                "  revel_score_min: 0.5\n"
                "  spliceai_delta_min: 0.2\n"
                "  ensemble_confidence_min: 0.85\n"
                "  sv_min_callers: 2\n"
                "  sv_min_supporting_reads: 5\n"
                "  sv_max_length_bp: 10_000_000\n"
                "  gnomad_af_max: 0.01\n"
                "Effective date: 2024-08-01. Reviewed and approved by clinical "
                "genomics lead. Last validated against ClinVar 2024-07 release."
            ),
            "tags": ["config", "thresholds", "production", "classifier", "genomics"],
            "metadata": {
                "effective_date": "2024-08-01",
                "cadd_phred_min": 20,
                "ensemble_confidence_min": 0.85,
            },
        },
        # ── C10 TEMPLATE ─────────────────────────────────────────────
        {
            "title": "Clinical Genomics Report Template",
            "type": CapsuleType.TEMPLATE,
            "content": (
                "# Clinical Genomics Report\n\n"
                "## Patient Information\n"
                "- MRN: {{patient_mrn}}\n"
                "- Referral Reason: {{referral_reason}}\n\n"
                "## Methodology\n"
                "Sequencing performed on {{platform}} with {{coverage}}x mean "
                "coverage. Variant classification uses ensemble classifier v{{version}}.\n\n"
                "## Findings\n"
                "### Pathogenic / Likely Pathogenic Variants\n"
                "{{#each plp_variants}}\n"
                "- **{{gene}}** {{hgvs_c}} ({{hgvs_p}}) — {{classification}}\n"
                "{{/each}}\n\n"
                "### Variants of Uncertain Significance\n"
                "{{#each vus_variants}}\n"
                "- **{{gene}}** {{hgvs_c}} — VUS (ensemble score: {{score}})\n"
                "{{/each}}\n\n"
                "## Recommendations\n"
                "{{recommendations}}\n\n"
                "Signed: {{signed_by}}, {{signed_date}}"
            ),
            "tags": ["template", "clinical", "reporting", "genomics", "report"],
            "metadata": {"format": "handlebars", "sections": 4},
        },
        # ── C11 DOCUMENT ─────────────────────────────────────────────
        {
            "title": "Comprehensive Genomics Platform Review",
            "type": CapsuleType.DOCUMENT,
            "content": (
                "Comprehensive review of the Forge genomics knowledge platform. "
                "Covers all layers: data ingestion (VCF, CRAM, FHIR), variant "
                "classification (ensemble model from C4), ontology (C1), and "
                "governance (decision C3). Performance benchmarks: 99.7% uptime, "
                "p95 query latency 120 ms, embedding-search recall 0.94 at k=10. "
                "Gap analysis: (1) no automated re-analysis pipeline, (2) limited "
                "pharmacogenomics coverage (340 of 1,500 known drug-gene pairs), "
                "(3) no structural variant visualization module. Roadmap proposes "
                "PrimeKG integration, FHIR R5 upgrade, and federated learning for "
                "cross-institutional variant sharing. This document extends the "
                "ontology in C1 with operational context."
            ),
            "tags": ["document", "review", "platform", "genomics", "architecture"],
            "metadata": {"uptime_pct": 99.7, "p95_latency_ms": 120},
        },
    ]


CAPSULE_DEFS: list[dict] = _capsule_defs()

# Symbolic names so tests can reference capsules by role
C1, C2, C3, C4, C5, C6, C7, C8, C9, C10, C11 = range(11)

# ═══════════════════════════════════════════════════════════════════════════════
# SEMANTIC EDGE DEFINITIONS
#
# Each edge is (source_index, target_index, relationship_type, extra_props).
# ═══════════════════════════════════════════════════════════════════════════════

EDGE_DEFS: list[tuple[int, int, SemanticRelationType, dict]] = [
    # C2 derives from C1 (insight from ontology)
    (C2, C1, SemanticRelationType.SUPPORTS, {"evidence_type": EvidenceType.EMPIRICAL.value}),
    # C5 derives from C2 (lesson from the analysis)
    (C5, C2, SemanticRelationType.REFERENCES, {}),
    # C4 implements C3 (code implements decision)
    (C4, C3, SemanticRelationType.IMPLEMENTS, {}),
    # C2 supports C3 (analysis backs the decision)
    (C2, C3, SemanticRelationType.SUPPORTS, {"evidence_type": EvidenceType.EMPIRICAL.value}),
    # C6 contradicts C2 (warning about yield inflation)
    (
        C6,
        C2,
        SemanticRelationType.CONTRADICTS,
        {
            "severity": ContradictionSeverity.HIGH.value,
            "resolution_status": "unresolved",
        },
    ),
    # C8 references C4, C5, C6 (memory)
    (C8, C4, SemanticRelationType.REFERENCES, {}),
    (C8, C5, SemanticRelationType.REFERENCES, {}),
    (C8, C6, SemanticRelationType.REFERENCES, {}),
    # C9 references C4 and C5 (config references code and lesson)
    (C9, C4, SemanticRelationType.REFERENCES, {}),
    (C9, C5, SemanticRelationType.REFERENCES, {}),
    # C11 extends C1 (document extends ontology)
    (C11, C1, SemanticRelationType.EXTENDS, {}),
    # C7 elaborates C1 (principle elaborates ontology)
    (C7, C1, SemanticRelationType.ELABORATES, {}),
    # C10 related to C4 (report template uses the classifier)
    (C10, C4, SemanticRelationType.RELATED_TO, {}),
]

# ═══════════════════════════════════════════════════════════════════════════════
# LINEAGE (DERIVED_FROM) DEFINITIONS
#
# (child_index, parent_index, evolution_reason)
# ═══════════════════════════════════════════════════════════════════════════════

LINEAGE_DEFS: list[tuple[int, int, str]] = [
    (C2, C1, "Insight derived from analysing the ontology dataset"),
    (C5, C2, "Lesson learned during the WGS diagnostic yield analysis"),
    (C11, C1, "Platform review document extending the ontology"),
]

# ═══════════════════════════════════════════════════════════════════════════════
# TOKENIZATION CONFIGURATIONS
#
# (capsule_index, token_name, token_symbol, initial_stake)
# ═══════════════════════════════════════════════════════════════════════════════

TOKENIZATION_CONFIGS: list[tuple[int, str, str, float]] = [
    (C1, "Genomic Ontology Token", "GOT", 100.0),
    (C4, "Variant Classifier Token", "VCT", 200.0),
]
