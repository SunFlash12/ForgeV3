"""
Tests for LLM Service

Tests cover:
- Mock provider functionality
- Ghost Council reviews
- Constitutional AI reviews
- Capsule analysis
- Error handling
"""


import pytest

from forge.services.llm import (
    LLMConfig,
    LLMMessage,
    LLMProvider,
    LLMResponse,
    LLMService,
)


class TestLLMConfig:
    """Tests for LLM configuration."""

    def test_default_config(self):
        config = LLMConfig()
        assert config.provider == LLMProvider.MOCK
        assert config.max_tokens == 4096
        assert config.temperature == 0.7

    def test_custom_config(self):
        config = LLMConfig(
            provider=LLMProvider.ANTHROPIC,
            model="claude-opus-4-20250514",
            api_key="test-key",
            max_tokens=8192,
            temperature=0.5,
        )
        assert config.provider == LLMProvider.ANTHROPIC
        assert config.model == "claude-opus-4-20250514"
        assert config.max_tokens == 8192


class TestMockLLMProvider:
    """Tests for mock LLM provider."""

    @pytest.fixture
    def service(self):
        config = LLMConfig(provider=LLMProvider.MOCK)
        return LLMService(config)

    @pytest.mark.asyncio
    async def test_complete_basic(self, service):
        messages = [
            LLMMessage(role="user", content="Hello, how are you?"),
        ]

        response = await service.complete(messages)

        assert isinstance(response, LLMResponse)
        assert response.model == "mock-llm"
        assert len(response.content) > 0
        assert response.finish_reason == "stop"

    @pytest.mark.asyncio
    async def test_complete_with_system(self, service):
        messages = [
            LLMMessage(role="system", content="You are a helpful assistant."),
            LLMMessage(role="user", content="What is AI?"),
        ]

        response = await service.complete(messages)

        assert isinstance(response, LLMResponse)
        assert len(response.content) > 0


class TestGhostCouncil:
    """Tests for Ghost Council review functionality."""

    @pytest.fixture
    def service(self):
        config = LLMConfig(provider=LLMProvider.MOCK)
        return LLMService(config)

    @pytest.mark.asyncio
    async def test_ghost_council_review(self, service):
        result = await service.ghost_council_review(
            proposal_title="Add new overlay capability",
            proposal_description="This proposal adds FILE_WRITE capability to overlays.",
            proposal_type="policy",
            proposer_trust=75,
        )

        assert "recommendation" in result
        assert result["recommendation"] in ["approve", "reject", "abstain"]
        assert "confidence" in result
        assert 0.0 <= result["confidence"] <= 1.0
        assert "reasoning" in result
        assert isinstance(result["reasoning"], list)

    @pytest.mark.asyncio
    async def test_ghost_council_with_context(self, service):
        context = {
            "related_proposals": ["prop-001", "prop-002"],
            "system_state": "healthy",
        }

        result = await service.ghost_council_review(
            proposal_title="Update trust thresholds",
            proposal_description="Lower minimum trust for voting to 50.",
            proposal_type="parameter",
            proposer_trust=85,
            context=context,
        )

        assert "recommendation" in result
        assert "model" in result

    @pytest.mark.asyncio
    async def test_ghost_council_low_trust_proposer(self, service):
        """Test review with low-trust proposer."""
        result = await service.ghost_council_review(
            proposal_title="Grant admin access",
            proposal_description="Give all users admin privileges.",
            proposal_type="policy",
            proposer_trust=30,
        )

        # Should still return valid response
        assert "recommendation" in result


class TestConstitutionalAI:
    """Tests for Constitutional AI review functionality."""

    @pytest.fixture
    def service(self):
        config = LLMConfig(provider=LLMProvider.MOCK)
        return LLMService(config)

    @pytest.mark.asyncio
    async def test_constitutional_review_capsule(self, service):
        result = await service.constitutional_review(
            content="This is a knowledge capsule about Python best practices.",
            content_type="capsule",
            action="create",
            actor_trust=70,
        )

        assert "compliant" in result
        assert isinstance(result["compliant"], bool)
        assert "score" in result
        assert 0.0 <= result["score"] <= 1.0
        assert "principles_evaluated" in result

    @pytest.mark.asyncio
    async def test_constitutional_review_proposal(self, service):
        result = await service.constitutional_review(
            content="Proposal to restrict certain user actions based on trust.",
            content_type="proposal",
            action="create",
            actor_trust=80,
        )

        assert "compliant" in result
        assert "severity" in result
        assert result["severity"] in ["none", "low", "medium", "high", "critical"]

    @pytest.mark.asyncio
    async def test_constitutional_review_with_context(self, service):
        context = {
            "previous_violations": 0,
            "actor_history": "good standing",
        }

        result = await service.constitutional_review(
            content="Modifying system parameters.",
            content_type="overlay",
            action="execute",
            actor_trust=85,
            context=context,
        )

        assert "reviewed_at" in result


class TestCapsuleAnalysis:
    """Tests for capsule content analysis."""

    @pytest.fixture
    def service(self):
        config = LLMConfig(provider=LLMProvider.MOCK)
        return LLMService(config)

    @pytest.mark.asyncio
    async def test_analyze_capsule(self, service):
        result = await service.analyze_capsule(
            content="This article explains the fundamentals of machine learning...",
            capsule_type="knowledge",
        )

        assert "summary" in result
        assert "topics" in result
        assert "sentiment" in result
        assert "quality_score" in result

    @pytest.mark.asyncio
    async def test_analyze_capsule_with_tags(self, service):
        result = await service.analyze_capsule(
            content="Python code examples for async programming.",
            capsule_type="code",
            existing_tags=["python", "programming"],
        )

        assert "suggested_tags" in result

    @pytest.mark.asyncio
    async def test_analyze_long_content(self, service):
        """Test analysis with very long content (truncation)."""
        long_content = "A" * 10000  # 10KB of content

        result = await service.analyze_capsule(
            content=long_content,
            capsule_type="knowledge",
        )

        # Should still work with truncated content
        assert "summary" in result


class TestLLMErrorHandling:
    """Tests for error handling."""

    @pytest.fixture
    def service(self):
        config = LLMConfig(
            provider=LLMProvider.MOCK,
            max_retries=2,
        )
        return LLMService(config)

    @pytest.mark.asyncio
    async def test_empty_messages(self, service):
        """Test with empty message list."""
        messages = []

        # Should handle gracefully
        response = await service.complete(messages)
        assert isinstance(response, LLMResponse)
