"""
Progressive Profiling
=====================

Gradually learns user preferences and behaviors to improve
system recommendations and personalization over time.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class InteractionType(Enum):
    """Types of user interactions."""

    CREATE_CAPSULE = "create_capsule"
    UPDATE_CAPSULE = "update_capsule"
    VIEW_CAPSULE = "view_capsule"
    SEARCH = "search"
    VOTE = "vote"
    COMMENT = "comment"
    SHARE = "share"
    BOOKMARK = "bookmark"


@dataclass
class UserInteraction:
    """Records a single user interaction."""

    interaction_id: str
    user_id: str
    interaction_type: InteractionType
    target_id: str | None  # Capsule ID, proposal ID, etc.
    timestamp: datetime = field(default_factory=datetime.utcnow)
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class TopicAffinity:
    """User affinity for a topic."""

    topic: str
    score: float  # 0.0 to 1.0
    interaction_count: int = 0
    last_interaction: datetime | None = None

    def decay(self, days_since: int, decay_rate: float = 0.05) -> float:
        """Apply time-based decay to affinity score."""
        return self.score * (1 - decay_rate) ** days_since


@dataclass
class UserProfile:
    """User profile built from interactions."""

    user_id: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_updated: datetime = field(default_factory=datetime.utcnow)

    # Topic affinities
    topic_affinities: dict[str, TopicAffinity] = field(default_factory=dict)

    # Behavioral patterns
    preferred_capsule_types: dict[str, int] = field(default_factory=dict)
    active_hours: dict[int, int] = field(default_factory=dict)  # hour -> count
    active_days: dict[int, int] = field(default_factory=dict)    # weekday -> count

    # Interaction history
    total_interactions: int = 0
    interactions_by_type: dict[str, int] = field(default_factory=dict)

    # Engagement metrics
    avg_session_duration_minutes: float = 0.0
    capsules_created: int = 0
    searches_performed: int = 0

    # Profile completeness (0.0 to 1.0)
    completeness: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat(),
            "last_updated": self.last_updated.isoformat(),
            "top_topics": self.get_top_topics(5),
            "preferred_types": dict(self.preferred_capsule_types),
            "total_interactions": self.total_interactions,
            "completeness": self.completeness,
            "engagement": {
                "capsules_created": self.capsules_created,
                "searches": self.searches_performed,
            }
        }

    def get_top_topics(self, n: int = 5) -> list[dict[str, Any]]:
        """Get top N topics by affinity."""
        sorted_topics = sorted(
            self.topic_affinities.items(),
            key=lambda x: x[1].score,
            reverse=True
        )
        return [
            {"topic": topic, "score": affinity.score}
            for topic, affinity in sorted_topics[:n]
        ]


class ProgressiveProfiler:
    """
    Builds user profiles progressively from interactions.

    Features:
    - Gradual profile building without upfront requirements
    - Topic affinity learning from interactions
    - Behavioral pattern detection
    - Time-based score decay
    """

    def __init__(
        self,
        decay_rate: float = 0.05,
        min_interactions_for_recommendations: int = 10
    ):
        self._decay_rate = decay_rate
        self._min_interactions = min_interactions_for_recommendations
        self._profiles: dict[str, UserProfile] = {}
        self._interactions: dict[str, list[UserInteraction]] = defaultdict(list)

        # Topic extraction patterns
        self._stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "must", "shall",
            "can", "this", "that", "these", "those", "it", "its",
        }

    def get_or_create_profile(self, user_id: str) -> UserProfile:
        """Get or create a user profile."""
        if user_id not in self._profiles:
            self._profiles[user_id] = UserProfile(user_id=user_id)
        return self._profiles[user_id]

    async def record_interaction(
        self,
        user_id: str,
        interaction_type: InteractionType,
        target_id: str | None = None,
        context: dict[str, Any] | None = None
    ) -> None:
        """
        Record a user interaction.

        Args:
            user_id: User who performed the action
            interaction_type: Type of interaction
            target_id: ID of target object (capsule, proposal, etc.)
            context: Additional context (content, tags, etc.)
        """
        interaction = UserInteraction(
            interaction_id=f"{user_id}_{datetime.utcnow().timestamp()}",
            user_id=user_id,
            interaction_type=interaction_type,
            target_id=target_id,
            context=context or {}
        )

        self._interactions[user_id].append(interaction)

        # Update profile
        profile = self.get_or_create_profile(user_id)
        self._update_profile(profile, interaction)

        logger.debug(
            "interaction_recorded",
            user_id=user_id,
            type=interaction_type.value
        )

    def _update_profile(
        self,
        profile: UserProfile,
        interaction: UserInteraction
    ) -> None:
        """Update profile based on interaction."""
        profile.total_interactions += 1
        profile.last_updated = datetime.utcnow()

        # Update interaction counts
        type_key = interaction.interaction_type.value
        profile.interactions_by_type[type_key] = profile.interactions_by_type.get(type_key, 0) + 1

        # Update active hours
        hour = interaction.timestamp.hour
        profile.active_hours[hour] = profile.active_hours.get(hour, 0) + 1

        # Update active days
        day = interaction.timestamp.weekday()
        profile.active_days[day] = profile.active_days.get(day, 0) + 1

        # Update specific metrics
        if interaction.interaction_type == InteractionType.CREATE_CAPSULE:
            profile.capsules_created += 1
            capsule_type = interaction.context.get("capsule_type", "UNKNOWN")
            profile.preferred_capsule_types[capsule_type] = profile.preferred_capsule_types.get(capsule_type, 0) + 1

        elif interaction.interaction_type == InteractionType.SEARCH:
            profile.searches_performed += 1

        # Extract and update topic affinities
        topics = self._extract_topics(interaction)
        for topic in topics:
            self._update_topic_affinity(profile, topic, interaction)

        # Recalculate profile completeness
        self._update_completeness(profile)

    def _extract_topics(self, interaction: UserInteraction) -> set[str]:
        """Extract topics from interaction context."""
        topics = set()

        # From explicit tags
        if "tags" in interaction.context:
            topics.update(interaction.context["tags"])

        # From content (simple word extraction)
        if "content" in interaction.context:
            content = interaction.context["content"]
            words = content.lower().split()
            # Extract significant words (basic approach)
            for word in words:
                word = ''.join(c for c in word if c.isalnum())
                if word and len(word) > 3 and word not in self._stop_words:
                    topics.add(word)

        # From capsule type
        if "capsule_type" in interaction.context:
            topics.add(f"type:{interaction.context['capsule_type']}")

        # From search query
        if "query" in interaction.context:
            query_words = interaction.context["query"].lower().split()
            for word in query_words:
                if len(word) > 2 and word not in self._stop_words:
                    topics.add(word)

        return topics

    def _update_topic_affinity(
        self,
        profile: UserProfile,
        topic: str,
        interaction: UserInteraction
    ) -> None:
        """Update affinity for a topic."""
        if topic not in profile.topic_affinities:
            profile.topic_affinities[topic] = TopicAffinity(
                topic=topic,
                score=0.0
            )

        affinity = profile.topic_affinities[topic]

        # Weights for different interaction types
        weights = {
            InteractionType.CREATE_CAPSULE: 1.0,
            InteractionType.UPDATE_CAPSULE: 0.8,
            InteractionType.BOOKMARK: 0.7,
            InteractionType.VOTE: 0.5,
            InteractionType.VIEW_CAPSULE: 0.3,
            InteractionType.SEARCH: 0.4,
            InteractionType.COMMENT: 0.6,
            InteractionType.SHARE: 0.8,
        }

        weight = weights.get(interaction.interaction_type, 0.3)

        # Update score (diminishing returns)
        old_score = affinity.score
        new_score = min(1.0, old_score + weight * (1 - old_score) * 0.1)

        affinity.score = new_score
        affinity.interaction_count += 1
        affinity.last_interaction = interaction.timestamp

    def _update_completeness(self, profile: UserProfile) -> None:
        """Calculate profile completeness."""
        completeness = 0.0

        # Has topics (30%)
        if len(profile.topic_affinities) >= 5:
            completeness += 0.3
        elif profile.topic_affinities:
            completeness += 0.3 * (len(profile.topic_affinities) / 5)

        # Has capsule type preferences (20%)
        if len(profile.preferred_capsule_types) >= 2:
            completeness += 0.2
        elif profile.preferred_capsule_types:
            completeness += 0.1

        # Has activity patterns (20%)
        if len(profile.active_hours) >= 3:
            completeness += 0.2
        elif profile.active_hours:
            completeness += 0.1

        # Has sufficient interactions (30%)
        if profile.total_interactions >= self._min_interactions:
            completeness += 0.3
        else:
            completeness += 0.3 * (profile.total_interactions / self._min_interactions)

        profile.completeness = min(1.0, completeness)

    def apply_decay(self, user_id: str) -> None:
        """Apply time-based decay to user profile scores."""
        profile = self._profiles.get(user_id)
        if not profile:
            return

        now = datetime.utcnow()

        for _topic, affinity in profile.topic_affinities.items():
            if affinity.last_interaction:
                days_since = (now - affinity.last_interaction).days
                if days_since > 0:
                    affinity.score = affinity.decay(days_since, self._decay_rate)

    def get_recommendations_ready(self, user_id: str) -> bool:
        """Check if profile has enough data for recommendations."""
        profile = self._profiles.get(user_id)
        if not profile:
            return False
        return profile.total_interactions >= self._min_interactions

    def get_topic_recommendations(
        self,
        user_id: str,
        n: int = 5
    ) -> list[str]:
        """Get recommended topics for a user."""
        profile = self._profiles.get(user_id)
        if not profile:
            return []

        # Get topics user has interacted with
        top_topics = profile.get_top_topics(n * 2)

        return [t["topic"] for t in top_topics[:n]]

    def get_similar_users(
        self,
        user_id: str,
        n: int = 5
    ) -> list[tuple[str, float]]:
        """Find users with similar profiles."""
        profile = self._profiles.get(user_id)
        if not profile:
            return []

        similarities = []

        for other_id, other_profile in self._profiles.items():
            if other_id == user_id:
                continue

            similarity = self._calculate_similarity(profile, other_profile)
            similarities.append((other_id, similarity))

        # Sort by similarity
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:n]

    def _calculate_similarity(
        self,
        profile1: UserProfile,
        profile2: UserProfile
    ) -> float:
        """Calculate similarity between two profiles."""
        # Topic similarity
        topics1 = set(profile1.topic_affinities.keys())
        topics2 = set(profile2.topic_affinities.keys())

        if not topics1 or not topics2:
            return 0.0

        intersection = topics1 & topics2
        union = topics1 | topics2

        jaccard = len(intersection) / len(union) if union else 0.0

        # Type preference similarity
        types1 = set(profile1.preferred_capsule_types.keys())
        types2 = set(profile2.preferred_capsule_types.keys())

        type_overlap = len(types1 & types2) / len(types1 | types2) if (types1 or types2) else 0.0

        # Weighted combination
        return jaccard * 0.7 + type_overlap * 0.3

    def get_profile_summary(self, user_id: str) -> dict[str, Any]:
        """Get a summary of user profile."""
        profile = self._profiles.get(user_id)
        if not profile:
            return {"error": "Profile not found"}

        return {
            "user_id": user_id,
            "profile_completeness": profile.completeness,
            "ready_for_recommendations": self.get_recommendations_ready(user_id),
            "top_topics": profile.get_top_topics(5),
            "favorite_capsule_types": sorted(
                profile.preferred_capsule_types.items(),
                key=lambda x: x[1],
                reverse=True
            )[:3],
            "total_interactions": profile.total_interactions,
            "member_since": profile.created_at.isoformat(),
        }


# Global instance
_progressive_profiler: ProgressiveProfiler | None = None


def get_progressive_profiler() -> ProgressiveProfiler:
    """Get or create the global progressive profiler instance."""
    global _progressive_profiler
    if _progressive_profiler is None:
        _progressive_profiler = ProgressiveProfiler()
    return _progressive_profiler


# Type hint for get_similar_users return
