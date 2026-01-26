"""
Differential Diagnosis Engine

The core engine for generating and refining differential diagnoses.
Integrates PrimeKG, HPO, genetic data, and Bayesian scoring.
"""

from dataclasses import dataclass
from datetime import UTC
from typing import Any, Protocol, runtime_checkable

import structlog

from .models import (
    DiagnosisHypothesis,
    DiagnosisResult,
    DiagnosisSession,
    DiagnosisState,
    EvidenceItem,
    EvidenceType,
    FollowUpQuestion,
    PatientProfile,
)
from .scoring import ScoringConfig, create_bayesian_scorer

logger = structlog.get_logger(__name__)


@runtime_checkable
class Neo4jClientProtocol(Protocol):
    async def run(self, query: str, params: dict[str, Any]) -> list[dict[str, Any]] | None: ...


@runtime_checkable
class HPOServiceProtocol(Protocol):
    def search_terms(self, text: str, limit: int = 10) -> list[Any]: ...
    def get_term(self, hpo_id: str) -> Any | None: ...


@dataclass
class EngineConfig:
    """Configuration for the diagnosis engine."""
    # Hypothesis generation
    max_hypotheses: int = 50
    min_phenotype_overlap: float = 0.2
    include_rare_diseases: bool = True

    # Scoring thresholds
    confidence_threshold: float = 0.7
    elimination_threshold: float = 0.05

    # Follow-up questions
    max_questions_per_iteration: int = 3
    min_information_gain: float = 0.1

    # Processing
    parallel_scoring: bool = True
    use_semantic_search: bool = True

    # Timeouts
    query_timeout: float = 30.0


class DiagnosisEngine:
    """
    Core engine for differential diagnosis generation.

    Workflow:
    1. Intake: Collect initial patient information
    2. Generate: Create candidate hypotheses from PrimeKG
    3. Score: Apply Bayesian scoring to all hypotheses
    4. Question: Generate discriminating follow-up questions
    5. Refine: Update scores based on new evidence
    6. Complete: Finalize when confident or max iterations reached
    """

    def __init__(
        self,
        config: EngineConfig | None = None,
        scoring_config: ScoringConfig | None = None,
        primekg_overlay: Any = None,
        hpo_service: Any = None,
        genetic_service: Any = None,
        neo4j_client: Any = None,
    ) -> None:
        """
        Initialize the diagnosis engine.

        Args:
            config: Engine configuration
            scoring_config: Scoring configuration
            primekg_overlay: PrimeKG overlay for disease queries
            hpo_service: HPO service for phenotype operations
            genetic_service: Genetic service for variant analysis
            neo4j_client: Neo4j client for direct queries
        """
        self.config = config or EngineConfig()
        self._primekg = primekg_overlay
        self._hpo = hpo_service
        self._genetic = genetic_service
        self._neo4j = neo4j_client

        # Initialize scorer
        self._scorer = create_bayesian_scorer(
            config=scoring_config,
            primekg_overlay=primekg_overlay,
        )

        # Active sessions
        self._sessions: dict[str, DiagnosisSession] = {}

    async def create_session(
        self,
        patient: PatientProfile | None = None,
        auto_advance: bool = True,
    ) -> DiagnosisSession:
        """
        Create a new diagnosis session.

        Args:
            patient: Optional initial patient profile
            auto_advance: Whether to auto-advance through states

        Returns:
            New diagnosis session
        """
        session = DiagnosisSession(
            patient=patient or PatientProfile(),
            auto_advance=auto_advance,
        )

        self._sessions[session.id] = session
        session.add_event("session_created", {"auto_advance": auto_advance})

        logger.info(
            "diagnosis_session_created",
            session_id=session.id,
            has_patient=patient is not None,
        )

        return session

    async def process_intake(
        self,
        session: DiagnosisSession,
        phenotypes: list[str] | None = None,
        genetic_variants: list[dict[str, Any]] | None = None,
        medical_history: list[str] | None = None,
        family_history: list[str] | None = None,
        demographics: dict[str, Any] | None = None,
    ) -> DiagnosisSession:
        """
        Process initial intake information.

        Args:
            session: Diagnosis session
            phenotypes: List of HPO codes or phenotype descriptions
            genetic_variants: List of variant dictionaries
            medical_history: List of medical history items
            family_history: List of family history items
            demographics: Patient demographics

        Returns:
            Updated session
        """
        session.state = DiagnosisState.INTAKE

        # Process demographics
        if demographics:
            session.patient.age = demographics.get("age")
            session.patient.age_of_onset = demographics.get("age_of_onset")
            session.patient.sex = demographics.get("sex")
            session.patient.ethnicity = demographics.get("ethnicity")

        # Process phenotypes
        if phenotypes:
            await self._process_phenotypes(session, phenotypes)

        # Process genetic variants
        if genetic_variants:
            await self._process_genetic_variants(session, genetic_variants)

        # Process medical history
        if medical_history:
            for item in medical_history:
                evidence = EvidenceItem(
                    evidence_type=EvidenceType.HISTORY,
                    value=item,
                )
                session.patient.medical_history.append(evidence)

        # Process family history
        if family_history:
            for item in family_history:
                evidence = EvidenceItem(
                    evidence_type=EvidenceType.FAMILY,
                    value=item,
                )
                session.patient.family_history.append(evidence)

        session.add_event("intake_processed", {
            "phenotype_count": len(session.patient.phenotypes),
            "variant_count": len(session.patient.genetic_variants),
            "history_count": len(session.patient.medical_history),
            "family_history_count": len(session.patient.family_history),
        })

        # Auto-advance to analysis
        if session.auto_advance:
            return await self.generate_hypotheses(session)

        return session

    async def _process_phenotypes(
        self,
        session: DiagnosisSession,
        phenotypes: list[str],
    ) -> None:
        """Process and normalize phenotype inputs."""
        for phenotype in phenotypes:
            # Check if HPO code
            is_hpo = phenotype.startswith("HP:")

            # Determine if negated
            negated = False
            clean_phenotype = phenotype
            if phenotype.startswith("NOT:") or phenotype.startswith("-"):
                negated = True
                clean_phenotype = phenotype.lstrip("NOT:").lstrip("-").strip()

            if is_hpo:
                # Direct HPO code
                evidence = EvidenceItem(
                    evidence_type=EvidenceType.PHENOTYPE,
                    code=clean_phenotype,
                    value=clean_phenotype,
                    negated=negated,
                )
            else:
                # Text description - try to map to HPO
                hpo_code = None
                if self._hpo:
                    try:
                        # search_terms is synchronous
                        matches = self._hpo.search_terms(clean_phenotype, limit=1)
                        if matches:
                            hpo_code = matches[0].hpo_id
                    except Exception as e:
                        logger.debug("hpo_mapping_failed", text=clean_phenotype, error=str(e))

                evidence = EvidenceItem(
                    evidence_type=EvidenceType.PHENOTYPE,
                    code=hpo_code,
                    value=clean_phenotype,
                    negated=negated,
                )

            session.patient.phenotypes.append(evidence)

    async def _process_genetic_variants(
        self,
        session: DiagnosisSession,
        variants: list[dict[str, Any]],
    ) -> None:
        """Process genetic variant inputs."""
        for var in variants:
            evidence = EvidenceItem(
                evidence_type=EvidenceType.GENETIC,
                value=var.get("notation", var.get("variant_id", "")),
                code=var.get("gene_symbol"),
                severity=var.get("pathogenicity"),
            )
            session.patient.genetic_variants.append(evidence)

    async def generate_hypotheses(
        self,
        session: DiagnosisSession,
    ) -> DiagnosisSession:
        """
        Generate candidate diagnosis hypotheses.

        Uses PrimeKG to find diseases matching:
        - Patient phenotypes
        - Affected genes (from variants)
        - Demographics (age of onset, inheritance)

        Args:
            session: Diagnosis session

        Returns:
            Updated session with hypotheses
        """
        session.state = DiagnosisState.ANALYZING

        hypotheses = []

        # Get phenotype-based candidates
        phenotype_candidates = await self._get_phenotype_candidates(session)
        hypotheses.extend(phenotype_candidates)

        # Get gene-based candidates
        gene_candidates = await self._get_gene_candidates(session)

        # Merge candidates (avoid duplicates)
        existing_ids = {h.disease_id for h in hypotheses}
        for candidate in gene_candidates:
            if candidate.disease_id not in existing_ids:
                hypotheses.append(candidate)
                existing_ids.add(candidate.disease_id)

        # Limit hypotheses
        hypotheses = hypotheses[:self.config.max_hypotheses]

        session.hypotheses = hypotheses

        session.add_event("hypotheses_generated", {
            "total_candidates": len(hypotheses),
            "from_phenotypes": len(phenotype_candidates),
            "from_genes": len(gene_candidates),
        })

        logger.info(
            "hypotheses_generated",
            session_id=session.id,
            count=len(hypotheses),
        )

        # Auto-advance to scoring
        if session.auto_advance:
            return await self.score_hypotheses(session)

        return session

    async def _get_phenotype_candidates(
        self,
        session: DiagnosisSession,
    ) -> list[DiagnosisHypothesis]:
        """Get candidate diseases based on phenotypes."""
        candidates: list[DiagnosisHypothesis] = []

        phenotype_codes = session.patient.phenotype_codes
        if not phenotype_codes:
            return candidates

        if not self._neo4j:
            return candidates

        # Query diseases with matching phenotypes
        query = """
        MATCH (d:PrimeKGDisease)-[:HAS_PHENOTYPE|PHENOTYPE_OF]-(p:PrimeKGPhenotype)
        WHERE p.hpo_id IN $phenotypes
        WITH d, collect(DISTINCT p.hpo_id) as matched_phenotypes, count(DISTINCT p) as match_count
        WHERE match_count >= $min_matches
        OPTIONAL MATCH (d)-[:ASSOCIATED_WITH|`associated with`]-(g:PrimeKGGene)
        WITH d, matched_phenotypes, match_count, collect(DISTINCT g.symbol) as genes
        RETURN d.mondo_id as disease_id,
               d.name as disease_name,
               d.description as description,
               matched_phenotypes,
               match_count,
               genes,
               d.prevalence as prevalence
        ORDER BY match_count DESC
        LIMIT $limit
        """

        min_matches = max(1, int(len(phenotype_codes) * self.config.min_phenotype_overlap))

        try:
            results = await self._neo4j.run(query, {
                "phenotypes": phenotype_codes,
                "min_matches": min_matches,
                "limit": self.config.max_hypotheses,
            })

            for r in (results or []):
                hypothesis = DiagnosisHypothesis(
                    disease_id=r["disease_id"] or "",
                    disease_name=r["disease_name"] or "Unknown",
                    description=r.get("description"),
                    matched_phenotypes=r.get("matched_phenotypes", []),
                    associated_genes=r.get("genes", []),
                    prior_probability=self._parse_prevalence(r.get("prevalence")),
                )

                # Calculate expected phenotypes
                hypothesis.expected_phenotypes = await self._get_expected_phenotypes(
                    hypothesis.disease_id
                )

                # Find missing phenotypes
                hypothesis.missing_phenotypes = [
                    p for p in hypothesis.expected_phenotypes
                    if p not in hypothesis.matched_phenotypes
                ]

                candidates.append(hypothesis)

        except Exception as e:
            logger.error("phenotype_candidate_query_failed", error=str(e))

        return candidates

    async def _get_gene_candidates(
        self,
        session: DiagnosisSession,
    ) -> list[DiagnosisHypothesis]:
        """Get candidate diseases based on genetic variants."""
        candidates: list[DiagnosisHypothesis] = []

        # Get genes from variants
        genes = []
        for var in session.patient.genetic_variants:
            if var.code:  # Gene symbol stored in code
                genes.append(var.code)

        if not genes or not self._neo4j:
            return candidates

        # Query diseases associated with these genes
        query = """
        MATCH (g:PrimeKGGene)-[r:ASSOCIATED_WITH|`associated with`]-(d:PrimeKGDisease)
        WHERE g.symbol IN $genes
        WITH d, collect(DISTINCT g.symbol) as matched_genes
        OPTIONAL MATCH (d)-[:HAS_PHENOTYPE|PHENOTYPE_OF]-(p:PrimeKGPhenotype)
        WITH d, matched_genes, collect(DISTINCT p.hpo_id) as phenotypes
        RETURN d.mondo_id as disease_id,
               d.name as disease_name,
               d.description as description,
               matched_genes,
               phenotypes,
               d.prevalence as prevalence
        ORDER BY size(matched_genes) DESC
        LIMIT $limit
        """

        try:
            results = await self._neo4j.run(query, {
                "genes": genes,
                "limit": self.config.max_hypotheses,
            })

            for r in (results or []):
                hypothesis = DiagnosisHypothesis(
                    disease_id=r["disease_id"] or "",
                    disease_name=r["disease_name"] or "Unknown",
                    description=r.get("description"),
                    associated_genes=r.get("matched_genes", []),
                    expected_phenotypes=r.get("phenotypes", []),
                    prior_probability=self._parse_prevalence(r.get("prevalence")),
                )
                candidates.append(hypothesis)

        except Exception as e:
            logger.error("gene_candidate_query_failed", error=str(e))

        return candidates

    async def _get_expected_phenotypes(
        self,
        disease_id: str,
        limit: int = 20,
    ) -> list[str]:
        """Get expected phenotypes for a disease."""
        if not self._neo4j or not disease_id:
            return []

        query = """
        MATCH (d:PrimeKGDisease)-[r:HAS_PHENOTYPE|PHENOTYPE_OF]-(p:PrimeKGPhenotype)
        WHERE d.mondo_id = $disease_id
        RETURN p.hpo_id as hpo_id, r.frequency as frequency
        ORDER BY r.frequency DESC
        LIMIT $limit
        """

        try:
            results = await self._neo4j.run(query, {
                "disease_id": disease_id,
                "limit": limit,
            })
            return [r["hpo_id"] for r in (results or []) if r.get("hpo_id")]
        except Exception as e:
            logger.debug("phenotype_query_failed", disease_id=disease_id, error=str(e))
            return []

    def _parse_prevalence(self, prevalence: Any) -> float:
        """Parse prevalence value to prior probability."""
        if prevalence is None:
            return 0.001  # Default 1 in 1000

        try:
            if isinstance(prevalence, int | float):
                return float(prevalence)
            if isinstance(prevalence, str):
                # Handle formats like "1/100000" or "0.00001"
                if "/" in prevalence:
                    parts = prevalence.split("/")
                    denominator = float(parts[1])
                    if denominator == 0:
                        return 0.001  # Default for invalid denominator
                    return float(parts[0]) / denominator
                return float(prevalence)
        except Exception as e:
            logger.debug("prevalence_parse_failed", input=str(prevalence)[:50], error=str(e))

        return 0.001

    async def score_hypotheses(
        self,
        session: DiagnosisSession,
    ) -> DiagnosisSession:
        """
        Score all hypotheses using Bayesian scoring.

        Args:
            session: Diagnosis session

        Returns:
            Updated session with scored hypotheses
        """
        if not session.hypotheses:
            return session

        # Score all hypotheses
        scored = await self._scorer.score_all_hypotheses(
            session.hypotheses,
            session.patient,
        )

        session.hypotheses = scored

        # Update top hypotheses
        session.top_hypotheses = [
            h for h in scored[:10]
            if h.combined_score >= self.config.elimination_threshold
        ]

        session.add_event("hypotheses_scored", {
            "total_scored": len(scored),
            "top_hypotheses": len(session.top_hypotheses),
            "top_score": session.top_hypotheses[0].combined_score if session.top_hypotheses else 0,
        })

        # Check if confident
        if session.is_confident:
            session.state = DiagnosisState.COMPLETE
            return session

        # Auto-advance to questioning
        if session.auto_advance:
            return await self.generate_questions(session)

        session.state = DiagnosisState.QUESTIONING
        return session

    async def generate_questions(
        self,
        session: DiagnosisSession,
    ) -> DiagnosisSession:
        """
        Generate discriminating follow-up questions.

        Selects questions that maximize information gain
        to discriminate between top hypotheses.

        Args:
            session: Diagnosis session

        Returns:
            Updated session with pending questions
        """
        session.state = DiagnosisState.QUESTIONING

        if len(session.top_hypotheses) <= 1:
            # No need for questions with single hypothesis
            session.state = DiagnosisState.COMPLETE
            return session

        questions = []

        # Get candidate phenotypes to ask about
        candidate_phenotypes = self._get_candidate_phenotypes(session)

        # Calculate information gain for each
        phenotype_scores = []
        for hpo_id in candidate_phenotypes:
            gain = self._scorer.calculate_information_gain(
                session.top_hypotheses,
                hpo_id,
            )
            if gain >= self.config.min_information_gain:
                phenotype_scores.append((hpo_id, gain))

        # Sort by information gain
        phenotype_scores.sort(key=lambda x: x[1], reverse=True)

        # Generate questions for top phenotypes
        for hpo_id, gain in phenotype_scores[:self.config.max_questions_per_iteration]:
            question = await self._create_phenotype_question(
                session, hpo_id, gain
            )
            if question:
                questions.append(question)

        # Add genetic question if relevant
        genetic_question = self._create_genetic_question(session)
        if genetic_question:
            questions.append(genetic_question)

        session.pending_questions = questions
        session.iterations += 1

        session.add_event("questions_generated", {
            "question_count": len(questions),
            "iteration": session.iterations,
        })

        return session

    def _get_candidate_phenotypes(
        self,
        session: DiagnosisSession,
    ) -> list[str]:
        """Get phenotypes to potentially ask about."""
        # Collect phenotypes from all top hypotheses
        all_phenotypes = set()
        for h in session.top_hypotheses:
            all_phenotypes.update(h.expected_phenotypes)
            all_phenotypes.update(h.missing_phenotypes)

        # Remove already known phenotypes
        known = set(session.patient.phenotype_codes)
        known.update(session.patient.negated_phenotype_codes)

        return list(all_phenotypes - known)

    async def _create_phenotype_question(
        self,
        session: DiagnosisSession,
        hpo_id: str,
        information_gain: float,
    ) -> FollowUpQuestion | None:
        """Create a question about a specific phenotype."""
        # Get phenotype name
        phenotype_name = hpo_id
        if self._hpo:
            try:
                term = self._hpo.get_term(hpo_id)
                if term:
                    phenotype_name = term.name
            except Exception as e:
                logger.debug("hpo_term_lookup_failed", hpo_id=hpo_id, error=str(e))

        # Find which hypotheses this affects
        affected = []
        for h in session.top_hypotheses:
            if hpo_id in h.expected_phenotypes or hpo_id in h.missing_phenotypes:
                affected.append(h.id)

        question = FollowUpQuestion(
            question_text=f"Does the patient have {phenotype_name}?",
            question_type="binary",
            target_phenotype=hpo_id,
            target_evidence="phenotype",
            options=[
                {"value": "yes", "label": "Yes"},
                {"value": "no", "label": "No"},
                {"value": "unknown", "label": "Unknown/Not assessed"},
            ],
            hypotheses_affected=affected,
            information_gain=information_gain,
            priority=1 if information_gain > 0.3 else 2,
        )

        return question

    def _create_genetic_question(
        self,
        session: DiagnosisSession,
    ) -> FollowUpQuestion | None:
        """Create a question about genetic testing."""
        # Only ask if genetic data might help and isn't available
        if session.patient.genetic_variants:
            return None

        # Check if any top hypothesis has associated genes
        genes = set()
        for h in session.top_hypotheses:
            genes.update(h.associated_genes)

        if not genes:
            return None

        gene_list = ", ".join(list(genes)[:5])

        return FollowUpQuestion(
            question_text=f"Has genetic testing been performed, particularly for genes: {gene_list}?",
            question_type="multiple_choice",
            target_evidence="genetic",
            options=[
                {"value": "not_done", "label": "No genetic testing done"},
                {"value": "negative", "label": "Testing done - no pathogenic variants"},
                {"value": "positive", "label": "Testing done - pathogenic variant(s) found"},
                {"value": "vus", "label": "Testing done - VUS found"},
            ],
            hypotheses_affected=[h.id for h in session.top_hypotheses],
            information_gain=0.5,
            priority=2,
        )

    async def answer_question(
        self,
        session: DiagnosisSession,
        question_id: str,
        answer: str,
        additional_info: dict[str, Any] | None = None,
    ) -> DiagnosisSession:
        """
        Process an answer to a follow-up question.

        Args:
            session: Diagnosis session
            question_id: ID of question being answered
            answer: User's answer
            additional_info: Optional additional information

        Returns:
            Updated session
        """
        # Find the question
        question = None
        for q in session.pending_questions:
            if q.id == question_id:
                question = q
                break

        if not question:
            logger.warning("question_not_found", question_id=question_id)
            return session

        # Record answer
        from datetime import datetime
        question.answer = answer
        question.answered_at = datetime.now(UTC)

        # Move to answered
        session.pending_questions.remove(question)
        session.answered_questions.append(question)

        # Process answer based on type
        if question.target_phenotype:
            await self._process_phenotype_answer(session, question, answer)
        elif question.target_evidence == "genetic":
            await self._process_genetic_answer(session, question, answer, additional_info)

        session.add_event("question_answered", {
            "question_id": question_id,
            "answer": answer,
            "target": question.target_phenotype or question.target_evidence,
        })

        # Re-score and continue
        session.state = DiagnosisState.REFINING
        return await self.score_hypotheses(session)

    async def _process_phenotype_answer(
        self,
        session: DiagnosisSession,
        question: FollowUpQuestion,
        answer: str,
    ) -> None:
        """Process answer to a phenotype question."""
        if answer == "unknown":
            return

        hpo_id = question.target_phenotype
        negated = answer == "no"

        evidence = EvidenceItem(
            evidence_type=EvidenceType.PHENOTYPE,
            code=hpo_id,
            value=question.question_text,
            negated=negated,
            confirmed=True,
        )

        session.patient.phenotypes.append(evidence)

    async def _process_genetic_answer(
        self,
        session: DiagnosisSession,
        question: FollowUpQuestion,
        answer: str,
        additional_info: dict[str, Any] | None,
    ) -> None:
        """Process answer to a genetic question."""
        if answer == "not_done":
            return

        if answer == "positive" and additional_info:
            # Add variant information
            for var in additional_info.get("variants", []):
                evidence = EvidenceItem(
                    evidence_type=EvidenceType.GENETIC,
                    value=var.get("notation", ""),
                    code=var.get("gene_symbol"),
                    severity="pathogenic",
                    confirmed=True,
                )
                session.patient.genetic_variants.append(evidence)

        elif answer == "vus" and additional_info:
            for var in additional_info.get("variants", []):
                evidence = EvidenceItem(
                    evidence_type=EvidenceType.GENETIC,
                    value=var.get("notation", ""),
                    code=var.get("gene_symbol"),
                    severity="uncertain_significance",
                    confirmed=True,
                )
                session.patient.genetic_variants.append(evidence)

    async def finalize_session(
        self,
        session: DiagnosisSession,
    ) -> DiagnosisResult:
        """
        Finalize a diagnosis session and generate result.

        Args:
            session: Diagnosis session

        Returns:
            Final diagnosis result
        """
        session.state = DiagnosisState.COMPLETE

        result = DiagnosisResult(
            session_id=session.id,
            patient_id=session.patient.id,
            primary_diagnosis=session.top_diagnosis,
            confidence=session.top_diagnosis.combined_score if session.top_diagnosis else 0.0,
            differential=session.top_hypotheses[:10],
            iterations=session.iterations,
            questions_asked=len(session.answered_questions),
            evidence_count=len(session.patient.all_evidence),
        )

        # Generate summary
        result.key_findings = self._generate_key_findings(session)
        result.recommended_tests = self._generate_recommended_tests(session)
        result.supporting_evidence_summary = self._generate_evidence_summary(session)

        session.add_event("session_finalized", {
            "primary_diagnosis": result.primary_diagnosis.disease_name if result.primary_diagnosis else None,
            "confidence": result.confidence,
            "differential_count": len(result.differential),
        })

        return result

    def _generate_key_findings(
        self,
        session: DiagnosisSession,
    ) -> list[str]:
        """Generate key findings from the session."""
        findings = []

        if session.top_diagnosis:
            top = session.top_diagnosis
            findings.append(
                f"Top diagnosis: {top.disease_name} "
                f"(confidence: {top.combined_score:.1%})"
            )

            if top.matched_phenotypes:
                findings.append(
                    f"Matched {len(top.matched_phenotypes)} expected phenotypes"
                )

            if top.supporting_evidence:
                findings.append(
                    f"{len(top.supporting_evidence)} pieces of supporting evidence"
                )

            if top.refuting_evidence:
                findings.append(
                    f"Note: {len(top.refuting_evidence)} potentially refuting findings"
                )

        return findings

    def _generate_recommended_tests(
        self,
        session: DiagnosisSession,
    ) -> list[str]:
        """Generate recommended confirmatory tests."""
        recommendations: list[str] = []

        if not session.top_diagnosis:
            return recommendations

        top = session.top_diagnosis

        # Recommend genetic testing if genes known but no variants
        if top.associated_genes and not session.patient.genetic_variants:
            genes = ", ".join(top.associated_genes[:3])
            recommendations.append(
                f"Consider genetic testing for: {genes}"
            )

        # Recommend checking missing phenotypes
        if top.missing_phenotypes:
            recommendations.append(
                f"Evaluate for {len(top.missing_phenotypes)} additional phenotypes"
            )

        return recommendations

    def _generate_evidence_summary(
        self,
        session: DiagnosisSession,
    ) -> str:
        """Generate a summary of supporting evidence."""
        if not session.top_diagnosis:
            return "Insufficient evidence for diagnosis"

        top = session.top_diagnosis
        parts = []

        parts.append(f"Evidence strength: {top.evidence_strength}")

        if top.phenotype_score > 0.5:
            parts.append("Strong phenotypic match")

        if top.genetic_score > 0.5:
            parts.append("Supporting genetic evidence")

        if top.history_score > 0.5:
            parts.append("Consistent with medical/family history")

        return ". ".join(parts)

    def get_session(self, session_id: str) -> DiagnosisSession | None:
        """Get a session by ID."""
        return self._sessions.get(session_id)

    def remove_session(self, session_id: str) -> bool:
        """Remove a session."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False


# =============================================================================
# Factory Function
# =============================================================================

def create_diagnosis_engine(
    config: EngineConfig | None = None,
    scoring_config: ScoringConfig | None = None,
    primekg_overlay: Any = None,
    hpo_service: Any = None,
    genetic_service: Any = None,
    neo4j_client: Any = None,
) -> DiagnosisEngine:
    """Create a diagnosis engine instance."""
    return DiagnosisEngine(
        config=config,
        scoring_config=scoring_config,
        primekg_overlay=primekg_overlay,
        hpo_service=hpo_service,
        genetic_service=genetic_service,
        neo4j_client=neo4j_client,
    )
