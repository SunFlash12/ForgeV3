"""
Phenotype Extractor Service

Extracts HPO phenotypes from clinical text using:
- Rule-based pattern matching
- Medical NER (Named Entity Recognition)
- LLM-based extraction
"""

import re
from dataclasses import dataclass
from typing import Any, Protocol

import structlog

from .models import (
    ExtractedPhenotype,
    PhenotypeMatch,
    PhenotypeSeverity,
)
from .ontology import HPOOntologyService

logger = structlog.get_logger(__name__)


class ExtractionProvider(Protocol):
    """Protocol for extraction providers."""

    async def extract(self, text: str) -> list[dict[str, Any]]:
        """Extract phenotypes from text."""
        ...


@dataclass
class ExtractionConfig:
    """Configuration for phenotype extraction."""
    min_confidence: float = 0.6
    extract_negations: bool = True
    extract_severity: bool = True
    extract_laterality: bool = True
    use_llm: bool = False
    llm_model: str = "gpt-4"
    max_text_length: int = 10000


class PhenotypeExtractor:
    """
    Service for extracting HPO phenotypes from clinical text.

    Supports multiple extraction methods:
    1. Rule-based: Pattern matching using HPO terms and synonyms
    2. NER-based: Medical Named Entity Recognition
    3. LLM-based: Large Language Model extraction
    """

    # Negation patterns
    NEGATION_PATTERNS = [
        r"\bno\s+(?:evidence\s+of\s+)?",
        r"\bwithout\s+",
        r"\bdenies\s+",
        r"\bdenied\s+",
        r"\bnegative\s+for\s+",
        r"\bnot\s+",
        r"\babsent\s+",
        r"\brules?\s+out\s+",
        r"\bunlikely\s+",
        r"\bno\s+signs?\s+of\s+",
    ]

    # Severity patterns
    SEVERITY_PATTERNS = {
        PhenotypeSeverity.MILD: [
            r"\bmild(ly)?\b", r"\bminor\b", r"\bslight(ly)?\b", r"\bsubtle\b"
        ],
        PhenotypeSeverity.MODERATE: [
            r"\bmoderate(ly)?\b", r"\bintermediate\b"
        ],
        PhenotypeSeverity.SEVERE: [
            r"\bsevere(ly)?\b", r"\bmarked(ly)?\b", r"\bpronounced\b",
            r"\bsignificant(ly)?\b", r"\bsubstantial(ly)?\b"
        ],
        PhenotypeSeverity.PROFOUND: [
            r"\bprofound(ly)?\b", r"\bextreme(ly)?\b", r"\bmassive\b"
        ],
    }

    # Laterality patterns
    LATERALITY_PATTERNS = {
        "left": [r"\bleft\b", r"\bL\s", r"\bsinistr"],
        "right": [r"\bright\b", r"\bR\s", r"\bdexter"],
        "bilateral": [r"\bbilateral(ly)?\b", r"\bboth\s+sides?\b"],
    }

    # Clinical section patterns
    SECTION_PATTERNS = {
        "chief_complaint": r"chief\s+complaint|cc:|presenting\s+complaint",
        "history": r"history\s+of\s+present\s+illness|hpi:|medical\s+history",
        "physical_exam": r"physical\s+exam(ination)?|pe:|exam:",
        "assessment": r"assessment:|impression:|diagnosis:",
        "plan": r"plan:|recommendations:|follow-?up:",
    }

    def __init__(
        self,
        ontology: HPOOntologyService,
        config: ExtractionConfig | None = None,
        llm_provider: ExtractionProvider | None = None,
    ):
        """
        Initialize the phenotype extractor.

        Args:
            ontology: HPO ontology service for term lookup
            config: Extraction configuration
            llm_provider: Optional LLM provider for enhanced extraction
        """
        self.ontology = ontology
        self.config = config or ExtractionConfig()
        self.llm_provider = llm_provider

        # Compile regex patterns
        self._negation_regex = re.compile(
            "|".join(self.NEGATION_PATTERNS),
            re.IGNORECASE
        )
        self._severity_regex = {
            severity: re.compile("|".join(patterns), re.IGNORECASE)
            for severity, patterns in self.SEVERITY_PATTERNS.items()
        }
        self._laterality_regex = {
            lat: re.compile("|".join(patterns), re.IGNORECASE)
            for lat, patterns in self.LATERALITY_PATTERNS.items()
        }
        self._section_regex = {
            section: re.compile(pattern, re.IGNORECASE)
            for section, pattern in self.SECTION_PATTERNS.items()
        }

    async def extract(
        self,
        text: str,
        context: dict[str, Any] | None = None,
    ) -> list[ExtractedPhenotype]:
        """
        Extract phenotypes from clinical text.

        Args:
            text: Clinical text to process
            context: Optional context (patient info, etc.)

        Returns:
            List of extracted phenotypes
        """
        if not text or not self.ontology.is_loaded:
            return []

        # Truncate if too long
        if len(text) > self.config.max_text_length:
            text = text[:self.config.max_text_length]

        logger.debug("phenotype_extraction_starting", text_length=len(text))

        # Detect sections
        sections = self._detect_sections(text)

        # Extract using rules
        rule_extractions = await self._extract_rule_based(text, sections)

        # Optionally enhance with LLM
        if self.config.use_llm and self.llm_provider:
            llm_extractions = await self._extract_llm_based(text, context)
            # Merge, preferring LLM for confidence
            rule_extractions = self._merge_extractions(rule_extractions, llm_extractions)

        # Filter by confidence
        filtered = [
            e for e in rule_extractions
            if e.confidence >= self.config.min_confidence
        ]

        logger.info(
            "phenotype_extraction_complete",
            total_found=len(rule_extractions),
            filtered=len(filtered),
        )

        return filtered

    async def _extract_rule_based(
        self,
        text: str,
        sections: dict[str, tuple[int, int]],
    ) -> list[ExtractedPhenotype]:
        """Extract phenotypes using rule-based pattern matching."""
        extractions = []
        text_lower = text.lower()

        # Iterate over all HPO terms
        for term in self.ontology.iter_terms():
            if term.is_obsolete:
                continue

            # Check for exact name match
            name_lower = term.name.lower()
            start_idx = text_lower.find(name_lower)

            if start_idx != -1:
                extraction = self._create_extraction(
                    text=text,
                    term=term,
                    match_text=term.name,
                    start_idx=start_idx,
                    match_type="exact",
                    confidence=0.95,
                    sections=sections,
                )
                extractions.append(extraction)
                continue

            # Check synonyms
            for synonym in term.synonyms:
                syn_lower = synonym.lower()
                start_idx = text_lower.find(syn_lower)

                if start_idx != -1:
                    extraction = self._create_extraction(
                        text=text,
                        term=term,
                        match_text=synonym,
                        start_idx=start_idx,
                        match_type="synonym",
                        confidence=0.85,
                        sections=sections,
                    )
                    extractions.append(extraction)
                    break

        # Deduplicate by HPO ID, keeping highest confidence
        seen = {}
        for ext in extractions:
            if ext.hpo_id not in seen or ext.confidence > seen[ext.hpo_id].confidence:
                seen[ext.hpo_id] = ext

        return list(seen.values())

    def _create_extraction(
        self,
        text: str,
        term,
        match_text: str,
        start_idx: int,
        match_type: str,
        confidence: float,
        sections: dict[str, tuple[int, int]],
    ) -> ExtractedPhenotype:
        """Create an ExtractedPhenotype with context analysis."""
        end_idx = start_idx + len(match_text)

        # Get surrounding context (50 chars before, 50 after)
        context_start = max(0, start_idx - 50)
        context_end = min(len(text), end_idx + 50)
        context = text[context_start:context_end]

        # Check for negation in context
        negated = False
        if self.config.extract_negations:
            # Look 30 chars before the match for negation
            neg_window = text[max(0, start_idx - 30):start_idx]
            negated = bool(self._negation_regex.search(neg_window))

        # Check for severity
        severity = PhenotypeSeverity.UNKNOWN
        if self.config.extract_severity:
            sev_window = text[max(0, start_idx - 30):min(len(text), end_idx + 30)]
            for sev, regex in self._severity_regex.items():
                if regex.search(sev_window):
                    severity = sev
                    break

        # Check for laterality
        laterality = None
        if self.config.extract_laterality:
            lat_window = text[max(0, start_idx - 20):min(len(text), end_idx + 20)]
            for lat, regex in self._laterality_regex.items():
                if regex.search(lat_window):
                    laterality = lat
                    break

        # Determine source section
        source_section = None
        for section_name, (sec_start, sec_end) in sections.items():
            if sec_start <= start_idx < sec_end:
                source_section = section_name
                break

        return ExtractedPhenotype(
            hpo_id=term.hpo_id,
            hpo_name=term.name,
            original_text=match_text,
            context=context,
            confidence=confidence,
            match_type=match_type,
            negated=negated,
            severity=severity,
            laterality=laterality,
            source_section=source_section,
            character_span=(start_idx, end_idx),
        )

    async def _extract_llm_based(
        self,
        text: str,
        context: dict[str, Any] | None,
    ) -> list[ExtractedPhenotype]:
        """Extract phenotypes using LLM."""
        if not self.llm_provider:
            return []

        try:
            results = await self.llm_provider.extract(text)
            extractions = []

            for result in results:
                hpo_id = result.get("hpo_id")
                if not hpo_id:
                    # Try to match by name
                    name = result.get("phenotype_name", "")
                    term = self.ontology.get_term_by_name(name)
                    if term:
                        hpo_id = term.hpo_id
                    else:
                        # Search for closest match
                        matches = self.ontology.search_terms(name, limit=1)
                        if matches:
                            hpo_id = matches[0].hpo_id

                if hpo_id:
                    term = self.ontology.get_term(hpo_id)
                    if term:
                        extractions.append(ExtractedPhenotype(
                            hpo_id=hpo_id,
                            hpo_name=term.name,
                            original_text=result.get("original_text", term.name),
                            context=result.get("context"),
                            confidence=result.get("confidence", 0.8),
                            match_type="llm",
                            negated=result.get("negated", False),
                            severity=PhenotypeSeverity(result.get("severity", "unknown")),
                            laterality=result.get("laterality"),
                        ))

            return extractions

        except Exception as e:
            logger.error("llm_extraction_failed", error=str(e))
            return []

    def _merge_extractions(
        self,
        rule_based: list[ExtractedPhenotype],
        llm_based: list[ExtractedPhenotype],
    ) -> list[ExtractedPhenotype]:
        """Merge rule-based and LLM extractions."""
        # Index rule-based by HPO ID
        merged = {e.hpo_id: e for e in rule_based}

        for llm_ext in llm_based:
            if llm_ext.hpo_id in merged:
                # Boost confidence if both methods found it
                existing = merged[llm_ext.hpo_id]
                existing.confidence = min(
                    1.0,
                    existing.confidence * 0.5 + llm_ext.confidence * 0.5 + 0.1
                )
            else:
                merged[llm_ext.hpo_id] = llm_ext

        return list(merged.values())

    def _detect_sections(self, text: str) -> dict[str, tuple[int, int]]:
        """Detect clinical sections in text."""
        sections = {}

        # Find all section headers
        section_starts = []
        for section_name, regex in self._section_regex.items():
            for match in regex.finditer(text):
                section_starts.append((match.start(), section_name))

        # Sort by position
        section_starts.sort(key=lambda x: x[0])

        # Create ranges
        for i, (start, name) in enumerate(section_starts):
            if i + 1 < len(section_starts):
                end = section_starts[i + 1][0]
            else:
                end = len(text)
            sections[name] = (start, end)

        return sections

    async def extract_from_structured(
        self,
        data: dict[str, Any],
    ) -> list[ExtractedPhenotype]:
        """
        Extract phenotypes from structured clinical data.

        Args:
            data: Dict with keys like "symptoms", "findings", "history"

        Returns:
            List of extracted phenotypes
        """
        extractions = []

        # Process known fields
        text_fields = [
            "symptoms",
            "findings",
            "chief_complaint",
            "history_of_present_illness",
            "physical_examination",
            "medical_history",
            "family_history",
        ]

        for field in text_fields:
            if field in data:
                value = data[field]
                if isinstance(value, str):
                    field_extractions = await self.extract(value)
                    for ext in field_extractions:
                        ext.source_section = field
                    extractions.extend(field_extractions)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, str):
                            field_extractions = await self.extract(item)
                            for ext in field_extractions:
                                ext.source_section = field
                            extractions.extend(field_extractions)

        # Handle pre-coded HPO terms
        if "hpo_terms" in data:
            for hpo_id in data["hpo_terms"]:
                term = self.ontology.get_term(hpo_id)
                if term:
                    extractions.append(ExtractedPhenotype(
                        hpo_id=hpo_id,
                        hpo_name=term.name,
                        original_text=term.name,
                        confidence=1.0,
                        match_type="provided",
                    ))

        # Deduplicate
        seen = {}
        for ext in extractions:
            if ext.hpo_id not in seen or ext.confidence > seen[ext.hpo_id].confidence:
                seen[ext.hpo_id] = ext

        return list(seen.values())


# =============================================================================
# LLM Extraction Provider
# =============================================================================

class OpenAIPhenotypeExtractor:
    """
    LLM-based phenotype extractor using OpenAI.

    Uses GPT-4 to identify phenotypes in clinical text.
    """

    EXTRACTION_PROMPT = """You are a medical phenotype extraction system. Extract Human Phenotype Ontology (HPO) terms from the following clinical text.

For each phenotype found, provide:
1. The HPO term name (e.g., "Seizure")
2. HPO ID if known (e.g., "HP:0001250")
3. Whether it's negated (e.g., "no seizures" = negated)
4. Severity if mentioned (mild, moderate, severe, profound)
5. Laterality if mentioned (left, right, bilateral)
6. The original text that indicates this phenotype

Return as JSON array:
[
  {
    "phenotype_name": "string",
    "hpo_id": "HP:XXXXXXX or null",
    "original_text": "string",
    "negated": boolean,
    "severity": "mild|moderate|severe|profound|unknown",
    "laterality": "left|right|bilateral|null",
    "confidence": 0.0-1.0
  }
]

Clinical Text:
{text}

JSON Output:"""

    def __init__(self, api_key: str, model: str = "gpt-4"):
        """Initialize with OpenAI API key."""
        try:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(api_key=api_key)
            self._model = model
        except ImportError:
            raise ImportError("openai package required for LLM extraction")

    async def extract(self, text: str) -> list[dict[str, Any]]:
        """Extract phenotypes using GPT-4."""
        import json

        prompt = self.EXTRACTION_PROMPT.format(text=text[:4000])  # Truncate

        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": "You are a medical phenotype extraction system."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=2000,
        )

        content = response.choices[0].message.content
        try:
            # Parse JSON from response
            return json.loads(content)
        except json.JSONDecodeError:
            logger.warning("llm_json_parse_failed", content=content[:200])
            return []


# =============================================================================
# Factory Function
# =============================================================================

def create_phenotype_extractor(
    ontology: HPOOntologyService,
    config: ExtractionConfig | None = None,
    openai_api_key: str | None = None,
) -> PhenotypeExtractor:
    """
    Create a phenotype extractor instance.

    Args:
        ontology: HPO ontology service
        config: Extraction configuration
        openai_api_key: OpenAI API key for LLM extraction

    Returns:
        Configured PhenotypeExtractor
    """
    llm_provider = None
    if openai_api_key and config and config.use_llm:
        llm_provider = OpenAIPhenotypeExtractor(
            api_key=openai_api_key,
            model=config.llm_model,
        )

    return PhenotypeExtractor(
        ontology=ontology,
        config=config,
        llm_provider=llm_provider,
    )
