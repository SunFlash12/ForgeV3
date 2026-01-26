"""
Medical History Extractor

Extracts structured history from clinical text and documents.
"""

import re
from dataclasses import dataclass
from typing import Any

import structlog

from .models import (
    FamilyMember,
    HistoryItem,
    HistoryTimeline,
    HistoryType,
    MedicationRecord,
    ProcedureRecord,
)

logger = structlog.get_logger(__name__)


@dataclass
class ExtractorConfig:
    """Configuration for history extraction."""

    use_nlp: bool = True
    use_llm: bool = False
    llm_model: str = "gpt-4"

    # Extraction settings
    extract_conditions: bool = True
    extract_medications: bool = True
    extract_procedures: bool = True
    extract_family_history: bool = True
    extract_allergies: bool = True

    # Confidence threshold
    min_confidence: float = 0.5


class HistoryExtractor:
    """
    Extracts medical history from clinical text.

    Supports:
    - Clinical notes
    - Discharge summaries
    - Problem lists
    - Family history sections
    - Medication lists
    """

    def __init__(
        self,
        config: ExtractorConfig | None = None,
        hpo_service: Any = None,
    ):
        """
        Initialize the history extractor.

        Args:
            config: Extractor configuration
            hpo_service: HPO service for phenotype mapping
        """
        self.config = config or ExtractorConfig()
        self._hpo = hpo_service

        # Patterns for extraction
        self._init_patterns()

    def _init_patterns(self) -> None:
        """Initialize regex patterns for extraction."""
        # Family member patterns
        self._family_patterns = {
            FamilyMember.MOTHER: r"\b(mother|mom|maternal)\b",
            FamilyMember.FATHER: r"\b(father|dad|paternal)\b",
            FamilyMember.SIBLING: r"\b(sibling|brother|sister)\b",
            FamilyMember.MATERNAL_GRANDMOTHER: r"\bmaternal\s+(grand)?mother\b",
            FamilyMember.MATERNAL_GRANDFATHER: r"\bmaternal\s+(grand)?father\b",
            FamilyMember.PATERNAL_GRANDMOTHER: r"\bpaternal\s+(grand)?mother\b",
            FamilyMember.PATERNAL_GRANDFATHER: r"\bpaternal\s+(grand)?father\b",
            FamilyMember.AUNT: r"\baunt\b",
            FamilyMember.UNCLE: r"\buncle\b",
            FamilyMember.COUSIN: r"\bcousin\b",
        }

        # Negation patterns
        self._negation_patterns = [
            r"\bno\s+",
            r"\bdenies\s+",
            r"\bnegative\s+for\s+",
            r"\bwithout\s+",
            r"\brules?\s+out\b",
            r"\babsent\b",
            r"\bnot\s+",
        ]

        # Severity patterns
        self._severity_patterns = {
            "mild": r"\bmild(ly)?\b",
            "moderate": r"\bmoderate(ly)?\b",
            "severe": r"\bsevere(ly)?\b",
            "profound": r"\bprofound(ly)?\b",
        }

        # Common condition patterns
        self._condition_keywords = [
            "diabetes",
            "hypertension",
            "cancer",
            "heart disease",
            "stroke",
            "seizure",
            "epilepsy",
            "asthma",
            "copd",
            "depression",
            "anxiety",
            "dementia",
            "alzheimer",
            "parkinson",
            "arthritis",
            "osteoporosis",
            "thyroid",
        ]

    async def extract_from_text(
        self,
        text: str,
        context: dict[str, Any] | None = None,
    ) -> HistoryTimeline:
        """
        Extract medical history from clinical text.

        Args:
            text: Clinical text to process
            context: Additional context (patient info, etc.)

        Returns:
            Extracted history timeline
        """
        timeline = HistoryTimeline()

        if context:
            timeline.patient_id = context.get("patient_id", "")
            timeline.sex = context.get("sex")

        # Extract different components
        if self.config.extract_conditions:
            conditions = await self._extract_conditions(text)
            timeline.conditions.extend(conditions)

        if self.config.extract_family_history:
            family = await self._extract_family_history(text)
            timeline.family_history.extend(family)

        if self.config.extract_medications:
            meds = self._extract_medications(text)
            timeline.medications.extend(meds)

        if self.config.extract_procedures:
            procedures = self._extract_procedures(text)
            timeline.procedures.extend(procedures)

        if self.config.extract_allergies:
            allergies = self._extract_allergies(text)
            timeline.allergies.extend(allergies)

        logger.info(
            "history_extracted",
            conditions=len(timeline.conditions),
            family_history=len(timeline.family_history),
            medications=len(timeline.medications),
        )

        return timeline

    async def _extract_conditions(
        self,
        text: str,
    ) -> list[HistoryItem]:
        """Extract medical conditions from text."""
        conditions = []
        text_lower = text.lower()

        # Section-based extraction
        sections = self._split_sections(text)

        # Look for problem list section
        problem_text = sections.get("problem_list", "") or sections.get("diagnoses", "") or text

        # Extract conditions using patterns
        for keyword in self._condition_keywords:
            if keyword in text_lower:
                # Find the sentence containing this condition
                for sentence in self._get_sentences(problem_text):
                    if keyword in sentence.lower():
                        condition = await self._parse_condition(sentence, keyword)
                        if condition:
                            conditions.append(condition)

        # Try HPO mapping if available
        if self._hpo:
            try:
                # Use HPO service to extract phenotypes
                pass  # Would integrate with HPO extractor
            except (RuntimeError, ValueError, OSError):
                pass

        return conditions

    async def _parse_condition(
        self,
        sentence: str,
        keyword: str,
    ) -> HistoryItem | None:
        """Parse a condition from a sentence."""
        # Check for negation
        is_negated = any(
            re.search(pattern, sentence, re.IGNORECASE) for pattern in self._negation_patterns
        )

        # Extract severity
        severity = None
        for sev, pattern in self._severity_patterns.items():
            if re.search(pattern, sentence, re.IGNORECASE):
                severity = sev
                break

        # Try to extract age of onset
        age_match = re.search(
            r"age\s*(\d+)|(\d+)\s*years?\s*old|since\s*age\s*(\d+)", sentence, re.IGNORECASE
        )
        age_at_onset = None
        if age_match:
            age_at_onset = int(next(g for g in age_match.groups() if g))

        condition = HistoryItem(
            history_type=HistoryType.CONDITION,
            description=sentence.strip(),
            is_negated=is_negated,
            severity=severity,
            age_at_onset=age_at_onset,
            source="text_extraction",
        )

        # Try HPO mapping (search_terms is synchronous)
        if self._hpo:
            try:
                matches = self._hpo.search_terms(keyword, limit=1)
                if matches:
                    condition.hpo_code = matches[0].hpo_id
            except (RuntimeError, ValueError, KeyError):
                pass

        return condition

    async def _extract_family_history(
        self,
        text: str,
    ) -> list[HistoryItem]:
        """Extract family history from text."""
        items = []

        # Find family history section
        sections = self._split_sections(text)
        fh_text = sections.get("family_history", "") or text

        # Look for family member mentions with conditions
        for member, pattern in self._family_patterns.items():
            matches = re.finditer(pattern, fh_text, re.IGNORECASE)
            for match in matches:
                # Get surrounding context
                start = max(0, match.start() - 50)
                end = min(len(fh_text), match.end() + 100)
                context = fh_text[start:end]

                # Look for conditions in context
                for keyword in self._condition_keywords:
                    if keyword in context.lower():
                        item = HistoryItem(
                            history_type=HistoryType.FAMILY,
                            description=context.strip(),
                            family_member=member,
                            source="text_extraction",
                        )

                        # Map to HPO if possible (search_terms is synchronous)
                        if self._hpo:
                            try:
                                hpo_matches = self._hpo.search_terms(keyword, limit=1)
                                if hpo_matches:
                                    item.hpo_code = hpo_matches[0].hpo_id
                            except (RuntimeError, ValueError, KeyError):
                                pass

                        items.append(item)
                        break

        return items

    def _extract_medications(
        self,
        text: str,
    ) -> list[MedicationRecord]:
        """Extract medications from text."""
        medications = []

        # Find medication section
        sections = self._split_sections(text)
        med_text = sections.get("medications", "") or text

        # Pattern for medication entries
        # e.g., "Metformin 500mg twice daily"
        med_pattern = r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*(\d+\s*(?:mg|mcg|g|ml|units?))?(?:\s+(once|twice|three times|four times|daily|bid|tid|qid|prn|as needed))?"

        matches = re.finditer(med_pattern, med_text)
        for match in matches:
            name = match.group(1)
            dose = match.group(2)
            frequency = match.group(3)

            # Skip if likely not a medication
            if name.lower() in ["the", "patient", "history", "family", "medical"]:
                continue

            med = MedicationRecord(
                medication_name=name,
                dose=dose,
                frequency=frequency,
            )
            medications.append(med)

        return medications

    def _extract_procedures(
        self,
        text: str,
    ) -> list[ProcedureRecord]:
        """Extract procedures from text."""
        procedures = []

        # Find surgical/procedure history section
        sections = self._split_sections(text)
        proc_text = sections.get("surgical_history", "") or sections.get("procedures", "") or text

        # Common procedure keywords
        proc_keywords = [
            "surgery",
            "operation",
            "procedure",
            "biopsy",
            "appendectomy",
            "cholecystectomy",
            "hysterectomy",
            "arthroscopy",
            "colonoscopy",
            "endoscopy",
            "cesarean",
            "c-section",
            "tonsillectomy",
        ]

        for keyword in proc_keywords:
            if keyword in proc_text.lower():
                for sentence in self._get_sentences(proc_text):
                    if keyword in sentence.lower():
                        proc = ProcedureRecord(
                            procedure_name=sentence.strip(),
                            procedure_type="surgery"
                            if "surgery" in keyword or keyword.endswith("ectomy")
                            else "procedure",
                        )

                        # Try to extract year
                        year_match = re.search(r"(19|20)\d{2}", sentence)
                        if year_match:
                            from datetime import date

                            proc.procedure_date = date(int(year_match.group()), 1, 1)

                        procedures.append(proc)
                        break

        return procedures

    def _extract_allergies(
        self,
        text: str,
    ) -> list[HistoryItem]:
        """Extract allergies from text."""
        allergies = []

        # Find allergy section
        sections = self._split_sections(text)
        allergy_text = sections.get("allergies", "") or text

        # Check for NKDA
        if re.search(r"\bNKDA\b|no\s+known\s+(drug\s+)?allergies", allergy_text, re.IGNORECASE):
            return []

        # Pattern for allergies
        # e.g., "Penicillin (rash)", "Sulfa - hives"

        # Common allergen keywords
        allergen_keywords = [
            "penicillin",
            "sulfa",
            "aspirin",
            "ibuprofen",
            "codeine",
            "morphine",
            "latex",
            "shellfish",
            "peanut",
            "egg",
            "milk",
            "soy",
            "wheat",
            "fish",
        ]

        for keyword in allergen_keywords:
            if keyword in allergy_text.lower():
                # Find context
                for sentence in self._get_sentences(allergy_text):
                    if keyword in sentence.lower():
                        allergy = HistoryItem(
                            history_type=HistoryType.ALLERGY,
                            description=sentence.strip(),
                            source="text_extraction",
                        )
                        allergies.append(allergy)
                        break

        return allergies

    def _split_sections(
        self,
        text: str,
    ) -> dict[str, str]:
        """Split text into sections based on headers."""
        sections = {}

        # Common section headers
        headers = [
            "problem list",
            "diagnoses",
            "medical history",
            "past medical history",
            "pmh",
            "family history",
            "fh",
            "medications",
            "current medications",
            "surgical history",
            "past surgical history",
            "psh",
            "procedures",
            "allergies",
            "social history",
        ]

        # Create pattern
        header_pattern = "|".join(re.escape(h) for h in headers)
        pattern = rf"(?:^|\n)\s*({header_pattern})\s*[:\n]"

        matches = list(re.finditer(pattern, text, re.IGNORECASE))

        for i, match in enumerate(matches):
            header = match.group(1).lower().replace(" ", "_")
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            sections[header] = text[start:end].strip()

        return sections

    def _get_sentences(self, text: str) -> list[str]:
        """Split text into sentences."""
        # Simple sentence splitting
        sentences = re.split(r"[.!?]\s+", text)
        return [s.strip() for s in sentences if s.strip()]


# =============================================================================
# Factory Function
# =============================================================================


def create_history_extractor(
    config: ExtractorConfig | None = None,
    hpo_service: Any = None,
) -> HistoryExtractor:
    """Create a history extractor instance."""
    return HistoryExtractor(
        config=config,
        hpo_service=hpo_service,
    )
