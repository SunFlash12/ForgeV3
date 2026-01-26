"""
Medical History Analyzer

Analyzes medical history for diagnostic relevance.
"""

from dataclasses import dataclass
from typing import Any

import structlog

from .models import (
    HistoryTimeline,
)

logger = structlog.get_logger(__name__)


@dataclass
class AnalyzerConfig:
    """Configuration for history analysis."""

    # Analysis weights
    family_history_weight: float = 0.3
    personal_history_weight: float = 0.5
    medication_relevance_weight: float = 0.2

    # Thresholds
    relevance_threshold: float = 0.3
    strong_family_history_threshold: int = 2  # Multiple affected relatives


class HistoryAnalyzer:
    """
    Analyzes medical history for diagnostic insights.

    Provides:
    - Family history pattern detection
    - Medication-condition correlations
    - Temporal pattern analysis
    - Diagnostic relevance scoring
    """

    def __init__(
        self,
        config: AnalyzerConfig | None = None,
        primekg_overlay: Any = None,
        neo4j_client: Any = None,
    ):
        """
        Initialize the history analyzer.

        Args:
            config: Analyzer configuration
            primekg_overlay: PrimeKG overlay for lookups
            neo4j_client: Neo4j client
        """
        self.config = config or AnalyzerConfig()
        self._primekg = primekg_overlay
        self._neo4j = neo4j_client

    async def analyze(
        self,
        timeline: HistoryTimeline,
    ) -> dict[str, Any]:
        """
        Analyze a medical history timeline.

        Args:
            timeline: Medical history timeline

        Returns:
            Analysis results
        """
        result = {
            "summary": self._generate_summary(timeline),
            "family_patterns": await self._analyze_family_patterns(timeline),
            "condition_clusters": self._identify_condition_clusters(timeline),
            "medication_insights": self._analyze_medications(timeline),
            "temporal_patterns": self._analyze_temporal_patterns(timeline),
            "diagnostic_hints": await self._generate_diagnostic_hints(timeline),
        }

        return result

    def _generate_summary(
        self,
        timeline: HistoryTimeline,
    ) -> dict[str, Any]:
        """Generate a summary of the medical history."""
        return {
            "total_conditions": len(timeline.conditions),
            "active_conditions": len(timeline.current_conditions),
            "family_history_items": len(timeline.family_history),
            "current_medications": len(timeline.current_medications),
            "total_procedures": len(timeline.procedures),
            "known_allergies": len(timeline.allergies),
            "has_developmental_history": len(timeline.developmental_history) > 0,
        }

    async def _analyze_family_patterns(
        self,
        timeline: HistoryTimeline,
    ) -> dict[str, Any]:
        """Analyze family history patterns."""
        patterns: dict[str, Any] = {
            "conditions_with_family_history": [],
            "inheritance_suggestions": [],
            "affected_relatives_by_condition": {},
            "strong_family_history": False,
        }

        # Group family history by condition
        condition_relatives: dict[str, list[str]] = {}
        for fh in timeline.family_history:
            description_lower = fh.description.lower()
            member = fh.family_member.value if fh.family_member else "unknown"

            # Check which conditions are mentioned
            for cond in timeline.conditions:
                cond_desc = cond.description.lower()
                # Simple matching - would use more sophisticated NLP
                keywords = cond_desc.split()[:3]  # First few words
                if any(kw in description_lower for kw in keywords if len(kw) > 3):
                    if cond_desc not in condition_relatives:
                        condition_relatives[cond_desc] = []
                    condition_relatives[cond_desc].append(member)

        patterns["affected_relatives_by_condition"] = condition_relatives

        # Identify conditions with strong family history
        for condition_name, relatives in condition_relatives.items():
            if len(relatives) >= self.config.strong_family_history_threshold:
                patterns["conditions_with_family_history"].append(
                    {
                        "condition": condition_name,
                        "affected_relatives": relatives,
                        "count": len(relatives),
                    }
                )
                patterns["strong_family_history"] = True

        # Suggest inheritance patterns
        if patterns["strong_family_history"]:
            patterns["inheritance_suggestions"] = self._suggest_inheritance_patterns(
                condition_relatives
            )

        return patterns

    def _suggest_inheritance_patterns(
        self,
        condition_relatives: dict[str, list[str]],
    ) -> list[dict[str, Any]]:
        """Suggest possible inheritance patterns based on family structure."""
        suggestions = []

        for condition, relatives in condition_relatives.items():
            relatives_set = set(relatives)

            # Check for vertical transmission (parent to child)
            if any(r in relatives_set for r in ["mother", "father"]):
                suggestions.append(
                    {
                        "condition": condition,
                        "pattern": "autosomal_dominant_possible",
                        "reasoning": "Affected parent suggests dominant inheritance",
                    }
                )

            # Check for horizontal transmission (siblings)
            if (
                "sibling" in relatives_set
                or "brother" in relatives_set
                or "sister" in relatives_set
            ):
                if not any(r in relatives_set for r in ["mother", "father"]):
                    suggestions.append(
                        {
                            "condition": condition,
                            "pattern": "autosomal_recessive_possible",
                            "reasoning": "Affected siblings without affected parents suggests recessive",
                        }
                    )

            # Check maternal line
            maternal = ["mother", "maternal_grandmother", "maternal_grandfather"]
            if sum(1 for r in maternal if r in relatives_set) >= 2:
                suggestions.append(
                    {
                        "condition": condition,
                        "pattern": "maternal_inheritance_possible",
                        "reasoning": "Multiple maternal relatives affected",
                    }
                )

        return suggestions

    def _identify_condition_clusters(
        self,
        timeline: HistoryTimeline,
    ) -> list[dict[str, Any]]:
        """Identify clusters of related conditions."""
        clusters = []

        # Simple clustering by temporal proximity
        conditions_by_onset = sorted(
            [c for c in timeline.conditions if c.age_at_onset],
            key=lambda x: x.age_at_onset or 0,
        )

        if len(conditions_by_onset) >= 2:
            current_cluster = [conditions_by_onset[0]]

            for i in range(1, len(conditions_by_onset)):
                current = conditions_by_onset[i]
                prev = conditions_by_onset[i - 1]

                # Same onset period (within 2 years)
                if (current.age_at_onset or 0) - (prev.age_at_onset or 0) <= 2:
                    current_cluster.append(current)
                else:
                    if len(current_cluster) >= 2:
                        clusters.append(
                            {
                                "conditions": [c.description for c in current_cluster],
                                "onset_period": f"Age {current_cluster[0].age_at_onset}",
                                "count": len(current_cluster),
                            }
                        )
                    current_cluster = [current]

            # Don't forget last cluster
            if len(current_cluster) >= 2:
                clusters.append(
                    {
                        "conditions": [c.description for c in current_cluster],
                        "onset_period": f"Age {current_cluster[0].age_at_onset}",
                        "count": len(current_cluster),
                    }
                )

        return clusters

    def _analyze_medications(
        self,
        timeline: HistoryTimeline,
    ) -> dict[str, Any]:
        """Analyze medication history for insights."""
        insights = {
            "current_medication_count": len(timeline.current_medications),
            "polypharmacy": len(timeline.current_medications) >= 5,
            "medication_categories": [],
            "potential_interactions": [],
        }

        # Categorize medications (simplified)
        categories: dict[str, list[str]] = {}
        for med in timeline.medications:
            # Simple categorization by name patterns
            name_lower = med.medication_name.lower()

            if any(kw in name_lower for kw in ["metformin", "insulin", "glipizide"]):
                cat = "diabetes"
            elif any(kw in name_lower for kw in ["lisinopril", "amlodipine", "metoprolol"]):
                cat = "cardiovascular"
            elif any(kw in name_lower for kw in ["sertraline", "fluoxetine", "lexapro"]):
                cat = "psychiatric"
            elif any(kw in name_lower for kw in ["levothyroxine", "synthroid"]):
                cat = "thyroid"
            else:
                cat = "other"

            if cat not in categories:
                categories[cat] = []
            categories[cat].append(med.medication_name)

        insights["medication_categories"] = [
            {"category": k, "medications": v, "count": len(v)} for k, v in categories.items()
        ]

        return insights

    def _analyze_temporal_patterns(
        self,
        timeline: HistoryTimeline,
    ) -> dict[str, Any]:
        """Analyze temporal patterns in the history."""
        patterns: dict[str, Any] = {
            "earliest_onset_age": None,
            "condition_progression": [],
            "age_periods": {},
        }

        # Find earliest onset
        onset_ages = [c.age_at_onset for c in timeline.conditions if c.age_at_onset]
        if onset_ages:
            patterns["earliest_onset_age"] = min(onset_ages)

        # Group by age periods
        periods: dict[str, tuple[int, int]] = {
            "childhood": (0, 12),
            "adolescence": (13, 18),
            "young_adult": (19, 40),
            "middle_age": (41, 65),
            "elderly": (66, 150),
        }

        for period_name, (start, end) in periods.items():
            conditions_in_period = [
                c for c in timeline.conditions if c.age_at_onset and start <= c.age_at_onset <= end
            ]
            if conditions_in_period:
                patterns["age_periods"][period_name] = {
                    "condition_count": len(conditions_in_period),
                    "conditions": [c.description for c in conditions_in_period[:5]],
                }

        return patterns

    async def _generate_diagnostic_hints(
        self,
        timeline: HistoryTimeline,
    ) -> list[dict[str, Any]]:
        """Generate diagnostic hints from the history."""
        hints = []

        # Hint from family history
        for fh in timeline.family_history:
            if fh.family_member and not fh.is_negated:
                hints.append(
                    {
                        "type": "family_history",
                        "description": f"Family history of condition in {fh.family_member.value}",
                        "detail": fh.description,
                        "relevance": "high"
                        if fh.family_member.value in ["mother", "father", "sibling"]
                        else "moderate",
                    }
                )

        # Hint from early onset conditions
        early_onset = [c for c in timeline.conditions if c.age_at_onset and c.age_at_onset < 18]
        if early_onset:
            hints.append(
                {
                    "type": "early_onset",
                    "description": "Early onset conditions (before age 18)",
                    "detail": f"{len(early_onset)} conditions with pediatric onset",
                    "relevance": "high",
                }
            )

        # Hint from condition clustering
        clusters = self._identify_condition_clusters(timeline)
        if clusters:
            for cluster in clusters:
                if cluster["count"] >= 3:
                    hints.append(
                        {
                            "type": "condition_cluster",
                            "description": "Multiple conditions with similar onset",
                            "detail": f"{cluster['count']} conditions at {cluster['onset_period']}",
                            "relevance": "moderate",
                        }
                    )

        # Query PrimeKG for disease associations if available
        if self._neo4j and timeline.phenotype_codes:
            try:
                # Look for diseases matching the phenotype profile
                query = """
                MATCH (d:PrimeKGDisease)-[:HAS_PHENOTYPE|PHENOTYPE_OF]-(p:PrimeKGPhenotype)
                WHERE p.hpo_id IN $codes
                WITH d, count(DISTINCT p) as matches
                WHERE matches >= $min_matches
                RETURN d.name as disease, matches
                ORDER BY matches DESC
                LIMIT 5
                """

                results = await self._neo4j.run(
                    query,
                    {
                        "codes": timeline.phenotype_codes,
                        "min_matches": max(1, len(timeline.phenotype_codes) // 2),
                    },
                )

                for r in results:
                    hints.append(
                        {
                            "type": "disease_association",
                            "description": f"Phenotype profile matches: {r['disease']}",
                            "detail": f"Matches {r['matches']} phenotypes",
                            "relevance": "high",
                        }
                    )

            except (RuntimeError, ValueError, OSError, ConnectionError) as e:
                logger.debug("disease_query_failed", error=str(e))

        return hints

    def calculate_diagnostic_relevance(
        self,
        timeline: HistoryTimeline,
        disease_name: str,
    ) -> float:
        """
        Calculate how relevant the history is to a specific disease.

        Args:
            timeline: Medical history timeline
            disease_name: Disease to check relevance for

        Returns:
            Relevance score (0-1)
        """
        score = 0.5  # Neutral baseline

        disease_lower = disease_name.lower()

        # Check family history
        for fh in timeline.family_history:
            if disease_lower in fh.description.lower():
                # Strong match in family history
                score += 0.2
                if fh.family_member and fh.family_member.value in ["mother", "father"]:
                    score += 0.1  # First-degree relative

        # Check personal history
        for condition in timeline.conditions:
            if disease_lower in condition.description.lower():
                if not condition.is_negated:
                    score += 0.3
                else:
                    score -= 0.2  # Negated condition

        # Clamp to 0-1
        return max(0.0, min(1.0, score))


# =============================================================================
# Factory Function
# =============================================================================


def create_history_analyzer(
    config: AnalyzerConfig | None = None,
    primekg_overlay: Any = None,
    neo4j_client: Any = None,
) -> HistoryAnalyzer:
    """Create a history analyzer instance."""
    return HistoryAnalyzer(
        config=config,
        primekg_overlay=primekg_overlay,
        neo4j_client=neo4j_client,
    )
