"""
Tests for Progressive Profiling
===============================

Tests for forge/resilience/cold_start/progressive_profiling.py
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from forge.resilience.cold_start.progressive_profiling import (
    InteractionType,
    ProgressiveProfiler,
    TopicAffinity,
    UserInteraction,
    UserProfile,
    get_progressive_profiler,
)


class TestInteractionType:
    """Tests for InteractionType enum."""

    def test_interaction_types(self):
        """Test all interaction types are defined."""
        assert InteractionType.CREATE_CAPSULE.value == "create_capsule"
        assert InteractionType.UPDATE_CAPSULE.value == "update_capsule"
        assert InteractionType.VIEW_CAPSULE.value == "view_capsule"
        assert InteractionType.SEARCH.value == "search"
        assert InteractionType.VOTE.value == "vote"
        assert InteractionType.COMMENT.value == "comment"
        assert InteractionType.SHARE.value == "share"
        assert InteractionType.BOOKMARK.value == "bookmark"


class TestUserInteraction:
    """Tests for UserInteraction dataclass."""

    def test_interaction_creation(self):
        """Test creating an interaction."""
        interaction = UserInteraction(
            interaction_id="int_123",
            user_id="user_456",
            interaction_type=InteractionType.CREATE_CAPSULE,
            target_id="cap_789",
        )

        assert interaction.interaction_id == "int_123"
        assert interaction.user_id == "user_456"
        assert interaction.interaction_type == InteractionType.CREATE_CAPSULE
        assert interaction.target_id == "cap_789"
        assert isinstance(interaction.timestamp, datetime)
        assert interaction.context == {}

    def test_interaction_with_context(self):
        """Test creating an interaction with context."""
        context = {"tags": ["test", "example"], "content": "Test content"}
        interaction = UserInteraction(
            interaction_id="int_123",
            user_id="user_456",
            interaction_type=InteractionType.SEARCH,
            target_id=None,
            context=context,
        )

        assert interaction.context == context


class TestTopicAffinity:
    """Tests for TopicAffinity dataclass."""

    def test_affinity_creation(self):
        """Test creating a topic affinity."""
        affinity = TopicAffinity(
            topic="machine-learning",
            score=0.8,
            interaction_count=10,
        )

        assert affinity.topic == "machine-learning"
        assert affinity.score == 0.8
        assert affinity.interaction_count == 10

    def test_decay_calculation(self):
        """Test affinity decay calculation."""
        affinity = TopicAffinity(topic="test", score=1.0)

        # 5 days with default 0.05 decay rate
        decayed = affinity.decay(5, 0.05)

        # Expected: 1.0 * (1 - 0.05)^5 = 0.77378...
        assert 0.77 <= decayed <= 0.78

    def test_decay_zero_days(self):
        """Test decay with zero days."""
        affinity = TopicAffinity(topic="test", score=0.5)

        decayed = affinity.decay(0, 0.1)

        assert decayed == 0.5

    def test_decay_high_rate(self):
        """Test decay with high decay rate."""
        affinity = TopicAffinity(topic="test", score=1.0)

        decayed = affinity.decay(10, 0.5)

        # Should be very small
        assert decayed < 0.01


class TestUserProfile:
    """Tests for UserProfile dataclass."""

    def test_profile_creation(self):
        """Test creating a user profile."""
        profile = UserProfile(user_id="user_123")

        assert profile.user_id == "user_123"
        assert isinstance(profile.created_at, datetime)
        assert profile.total_interactions == 0
        assert profile.completeness == 0.0

    def test_profile_to_dict(self):
        """Test converting profile to dict."""
        profile = UserProfile(
            user_id="user_123",
            total_interactions=50,
            capsules_created=10,
            searches_performed=20,
            completeness=0.75,
        )
        profile.preferred_capsule_types = {"KNOWLEDGE": 5, "DECISION": 3}

        result = profile.to_dict()

        assert result["user_id"] == "user_123"
        assert result["total_interactions"] == 50
        assert result["completeness"] == 0.75
        assert result["engagement"]["capsules_created"] == 10
        assert result["engagement"]["searches"] == 20

    def test_get_top_topics(self):
        """Test getting top topics."""
        profile = UserProfile(user_id="user_123")
        profile.topic_affinities = {
            "python": TopicAffinity(topic="python", score=0.9),
            "testing": TopicAffinity(topic="testing", score=0.7),
            "ai": TopicAffinity(topic="ai", score=0.5),
        }

        top = profile.get_top_topics(2)

        assert len(top) == 2
        assert top[0]["topic"] == "python"
        assert top[0]["score"] == 0.9
        assert top[1]["topic"] == "testing"


class TestProgressiveProfiler:
    """Tests for ProgressiveProfiler class."""

    @pytest.fixture
    def profiler(self):
        """Create a profiler instance."""
        return ProgressiveProfiler(
            decay_rate=0.05,
            min_interactions_for_recommendations=5,
        )

    def test_profiler_creation(self):
        """Test profiler creation with defaults."""
        profiler = ProgressiveProfiler()

        assert profiler._decay_rate == 0.05
        assert profiler._min_interactions == 10

    def test_get_or_create_profile_new(self, profiler):
        """Test creating a new profile."""
        profile = profiler.get_or_create_profile("user_123")

        assert profile.user_id == "user_123"
        assert "user_123" in profiler._profiles

    def test_get_or_create_profile_existing(self, profiler):
        """Test getting an existing profile."""
        profiler.get_or_create_profile("user_123")
        profile = profiler.get_or_create_profile("user_123")

        assert profile.user_id == "user_123"
        assert len(profiler._profiles) == 1

    @pytest.mark.asyncio
    async def test_record_interaction_creates_profile(self, profiler):
        """Test recording an interaction creates profile if needed."""
        await profiler.record_interaction(
            user_id="user_456",
            interaction_type=InteractionType.VIEW_CAPSULE,
            target_id="cap_123",
        )

        assert "user_456" in profiler._profiles
        assert profiler._profiles["user_456"].total_interactions == 1

    @pytest.mark.asyncio
    async def test_record_interaction_updates_counts(self, profiler):
        """Test recording interaction updates counts."""
        await profiler.record_interaction(
            user_id="user_123",
            interaction_type=InteractionType.CREATE_CAPSULE,
            context={"capsule_type": "KNOWLEDGE"},
        )

        profile = profiler._profiles["user_123"]
        assert profile.total_interactions == 1
        assert profile.capsules_created == 1
        assert profile.interactions_by_type["create_capsule"] == 1
        assert profile.preferred_capsule_types["KNOWLEDGE"] == 1

    @pytest.mark.asyncio
    async def test_record_interaction_updates_search_count(self, profiler):
        """Test recording search updates search count."""
        await profiler.record_interaction(
            user_id="user_123",
            interaction_type=InteractionType.SEARCH,
            context={"query": "test query"},
        )

        profile = profiler._profiles["user_123"]
        assert profile.searches_performed == 1

    @pytest.mark.asyncio
    async def test_record_interaction_extracts_topics_from_tags(self, profiler):
        """Test topic extraction from tags."""
        await profiler.record_interaction(
            user_id="user_123",
            interaction_type=InteractionType.VIEW_CAPSULE,
            context={"tags": ["python", "machine-learning"]},
        )

        profile = profiler._profiles["user_123"]
        assert "python" in profile.topic_affinities
        assert "machine-learning" in profile.topic_affinities

    @pytest.mark.asyncio
    async def test_record_interaction_extracts_topics_from_content(self, profiler):
        """Test topic extraction from content."""
        await profiler.record_interaction(
            user_id="user_123",
            interaction_type=InteractionType.CREATE_CAPSULE,
            context={"content": "Python testing framework discussion"},
        )

        profile = profiler._profiles["user_123"]
        # "python" and "testing" should be extracted (longer than 3 chars)
        assert "python" in profile.topic_affinities
        assert "testing" in profile.topic_affinities
        assert "framework" in profile.topic_affinities
        # Stop words should be excluded
        assert "the" not in profile.topic_affinities

    @pytest.mark.asyncio
    async def test_record_interaction_updates_active_hours(self, profiler):
        """Test recording interaction updates active hours."""
        await profiler.record_interaction(
            user_id="user_123",
            interaction_type=InteractionType.VIEW_CAPSULE,
        )

        profile = profiler._profiles["user_123"]
        current_hour = datetime.now(UTC).hour
        assert current_hour in profile.active_hours

    @pytest.mark.asyncio
    async def test_record_interaction_updates_active_days(self, profiler):
        """Test recording interaction updates active days."""
        await profiler.record_interaction(
            user_id="user_123",
            interaction_type=InteractionType.VIEW_CAPSULE,
        )

        profile = profiler._profiles["user_123"]
        current_day = datetime.now(UTC).weekday()
        assert current_day in profile.active_days

    @pytest.mark.asyncio
    async def test_topic_affinity_weights(self, profiler):
        """Test different interaction types have different weights."""
        await profiler.record_interaction(
            user_id="user_123",
            interaction_type=InteractionType.CREATE_CAPSULE,
            context={"tags": ["topic1"]},
        )

        profile1 = profiler._profiles["user_123"]
        score_create = profile1.topic_affinities["topic1"].score

        profiler2 = ProgressiveProfiler()
        await profiler2.record_interaction(
            user_id="user_456",
            interaction_type=InteractionType.VIEW_CAPSULE,
            context={"tags": ["topic1"]},
        )

        profile2 = profiler2._profiles["user_456"]
        score_view = profile2.topic_affinities["topic1"].score

        # CREATE should have higher weight than VIEW
        assert score_create > score_view

    def test_apply_decay(self, profiler):
        """Test applying decay to profile scores."""
        profile = profiler.get_or_create_profile("user_123")
        profile.topic_affinities["test"] = TopicAffinity(
            topic="test",
            score=1.0,
            last_interaction=datetime.now(UTC) - timedelta(days=10),
        )

        profiler.apply_decay("user_123")

        # Score should be decayed
        assert profile.topic_affinities["test"].score < 1.0

    def test_apply_decay_no_profile(self, profiler):
        """Test apply_decay with nonexistent profile."""
        # Should not raise
        profiler.apply_decay("nonexistent_user")

    def test_get_recommendations_ready_false(self, profiler):
        """Test recommendations not ready with few interactions."""
        profiler.get_or_create_profile("user_123")

        assert profiler.get_recommendations_ready("user_123") is False

    def test_get_recommendations_ready_true(self, profiler):
        """Test recommendations ready with enough interactions."""
        profile = profiler.get_or_create_profile("user_123")
        profile.total_interactions = 10

        assert profiler.get_recommendations_ready("user_123") is True

    def test_get_recommendations_ready_no_profile(self, profiler):
        """Test recommendations for nonexistent profile."""
        assert profiler.get_recommendations_ready("nonexistent") is False

    def test_get_topic_recommendations(self, profiler):
        """Test getting topic recommendations."""
        profile = profiler.get_or_create_profile("user_123")
        profile.topic_affinities = {
            "python": TopicAffinity(topic="python", score=0.9),
            "testing": TopicAffinity(topic="testing", score=0.7),
            "ai": TopicAffinity(topic="ai", score=0.5),
        }

        topics = profiler.get_topic_recommendations("user_123", n=2)

        assert len(topics) == 2
        assert "python" in topics
        assert "testing" in topics

    def test_get_topic_recommendations_no_profile(self, profiler):
        """Test topic recommendations for nonexistent profile."""
        topics = profiler.get_topic_recommendations("nonexistent")

        assert topics == []

    def test_get_similar_users_no_profile(self, profiler):
        """Test similar users for nonexistent profile."""
        similar = profiler.get_similar_users("nonexistent")

        assert similar == []

    def test_get_similar_users(self, profiler):
        """Test finding similar users."""
        profile1 = profiler.get_or_create_profile("user_1")
        profile1.topic_affinities = {
            "python": TopicAffinity(topic="python", score=0.9),
            "testing": TopicAffinity(topic="testing", score=0.7),
        }
        profile1.preferred_capsule_types = {"KNOWLEDGE": 5}

        profile2 = profiler.get_or_create_profile("user_2")
        profile2.topic_affinities = {
            "python": TopicAffinity(topic="python", score=0.8),
            "testing": TopicAffinity(topic="testing", score=0.6),
        }
        profile2.preferred_capsule_types = {"KNOWLEDGE": 3}

        profile3 = profiler.get_or_create_profile("user_3")
        profile3.topic_affinities = {
            "java": TopicAffinity(topic="java", score=0.9),
        }
        profile3.preferred_capsule_types = {"DECISION": 5}

        similar = profiler.get_similar_users("user_1", n=2)

        # user_2 should be more similar to user_1
        assert len(similar) == 2
        assert similar[0][0] == "user_2"
        assert similar[0][1] > similar[1][1]  # Higher similarity score

    def test_calculate_similarity_no_topics(self, profiler):
        """Test similarity calculation with no topics."""
        profile1 = UserProfile(user_id="user_1")
        profile2 = UserProfile(user_id="user_2")

        similarity = profiler._calculate_similarity(profile1, profile2)

        assert similarity == 0.0

    def test_get_profile_summary(self, profiler):
        """Test getting profile summary."""
        profile = profiler.get_or_create_profile("user_123")
        profile.total_interactions = 15
        profile.completeness = 0.8
        profile.topic_affinities = {
            "python": TopicAffinity(topic="python", score=0.9),
        }
        profile.preferred_capsule_types = {"KNOWLEDGE": 5}

        summary = profiler.get_profile_summary("user_123")

        assert summary["user_id"] == "user_123"
        assert summary["profile_completeness"] == 0.8
        assert summary["ready_for_recommendations"] is True
        assert summary["total_interactions"] == 15

    def test_get_profile_summary_not_found(self, profiler):
        """Test profile summary for nonexistent user."""
        summary = profiler.get_profile_summary("nonexistent")

        assert summary == {"error": "Profile not found"}

    @pytest.mark.asyncio
    async def test_update_completeness(self, profiler):
        """Test completeness calculation."""
        # Add enough interactions and data to reach high completeness
        for i in range(15):
            await profiler.record_interaction(
                user_id="user_123",
                interaction_type=InteractionType.CREATE_CAPSULE,
                context={
                    "tags": [f"topic{i % 6}"],
                    "capsule_type": "KNOWLEDGE" if i % 2 == 0 else "DECISION",
                },
            )

        profile = profiler._profiles["user_123"]

        # Should have decent completeness
        assert profile.completeness > 0.5


class TestGlobalFunctions:
    """Tests for module-level functions."""

    def test_get_progressive_profiler(self):
        """Test getting global profiler."""
        with patch(
            "forge.resilience.cold_start.progressive_profiling._progressive_profiler",
            None,
        ):
            profiler = get_progressive_profiler()

            assert isinstance(profiler, ProgressiveProfiler)
