"""
Tests for Resilience Integration
================================

Tests for forge/resilience/integration.py
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from forge.resilience.integration import (
    ObservabilityMiddleware,
    ResilienceState,
    cache_capsule,
    cache_governance_metrics,
    cache_health_status,
    cache_lineage,
    cache_overlay_list,
    cache_proposal,
    cache_proposals_list,
    cache_search_results,
    cache_system_metrics,
    check_content_validation,
    get_cached_capsule,
    get_cached_governance_metrics,
    get_cached_health_status,
    get_cached_lineage,
    get_cached_overlay_list,
    get_cached_proposal,
    get_cached_proposals_list,
    get_cached_search,
    get_cached_system_metrics,
    get_resilience_state,
    initialize_resilience,
    invalidate_capsule_cache,
    invalidate_overlay_cache,
    invalidate_proposal_cache,
    record_cache_hit,
    record_cache_miss,
    record_capsule_created,
    record_capsule_deleted,
    record_capsule_updated,
    record_lineage_query,
    record_login_attempt,
    record_proposal_created,
    record_search,
    record_vote_cast,
    shutdown_resilience,
    validate_capsule_content,
)
from forge.resilience.security.content_validator import ThreatLevel, ValidationResult


class TestResilienceState:
    """Tests for ResilienceState class."""

    def test_state_creation(self):
        """Test state creation."""
        state = ResilienceState()

        assert state.cache is None
        assert state.invalidator is None
        assert state.validator is None
        assert state.tracer is None
        assert state.metrics is None
        assert state.initialized is False

    @pytest.mark.asyncio
    async def test_initialize(self):
        """Test state initialization."""
        with patch("forge.resilience.integration.get_resilience_config") as mock_config:
            mock_config.return_value.cache.enabled = False
            mock_config.return_value.content_validation.enabled = False
            mock_config.return_value.observability.enabled = False

            state = ResilienceState()
            await state.initialize()

            assert state.initialized is True

    @pytest.mark.asyncio
    async def test_initialize_idempotent(self):
        """Test that initialize is idempotent."""
        with patch("forge.resilience.integration.get_resilience_config") as mock_config:
            mock_config.return_value.cache.enabled = False
            mock_config.return_value.content_validation.enabled = False
            mock_config.return_value.observability.enabled = False

            state = ResilienceState()
            await state.initialize()
            await state.initialize()

            assert state.initialized is True

    @pytest.mark.asyncio
    async def test_close(self):
        """Test closing state."""
        state = ResilienceState()
        state.cache = AsyncMock()
        state.invalidator = AsyncMock()
        state.initialized = True

        await state.close()

        state.cache.close.assert_called_once()
        state.invalidator.close.assert_called_once()
        assert state.initialized is False


class TestObservabilityMiddleware:
    """Tests for ObservabilityMiddleware class."""

    @pytest.fixture
    def middleware(self):
        """Create middleware instance."""
        app = MagicMock()
        return ObservabilityMiddleware(app)

    def test_get_path_template_capsule_id(self, middleware):
        """Test path template extraction for capsule IDs."""
        path = "/api/capsules/cap_abc123def456"
        result = middleware._get_path_template(path)
        assert result == "/api/capsules/{capsule_id}"

    def test_get_path_template_uuid(self, middleware):
        """Test path template extraction for UUIDs."""
        path = "/api/items/123e4567-e89b-12d3-a456-426614174000"
        result = middleware._get_path_template(path)
        assert result == "/api/items/{id}"

    def test_get_path_template_long_hex(self, middleware):
        """Test path template extraction for long hex IDs."""
        path = "/api/objects/507f1f77bcf86cd799439011"
        result = middleware._get_path_template(path)
        assert result == "/api/objects/{id}"

    def test_get_path_template_no_ids(self, middleware):
        """Test path template with no IDs."""
        path = "/api/health"
        result = middleware._get_path_template(path)
        assert result == "/api/health"


class TestCachingHelpers:
    """Tests for caching helper functions."""

    @pytest.fixture
    def mock_state(self):
        """Create mock resilience state."""
        state = ResilienceState()
        state.cache = AsyncMock()
        state.invalidator = AsyncMock()
        state.initialized = True
        return state

    @pytest.mark.asyncio
    async def test_get_cached_capsule(self, mock_state):
        """Test getting cached capsule."""
        mock_state.cache.get.return_value = {"id": "cap_123", "title": "Test"}

        with patch("forge.resilience.integration.get_resilience_state", return_value=mock_state):
            with patch("forge.resilience.integration.get_resilience_config") as mock_config:
                mock_config.return_value.cache.capsule_key_pattern = "forge:capsule:{capsule_id}"

                result = await get_cached_capsule("cap_123")

                assert result["id"] == "cap_123"

    @pytest.mark.asyncio
    async def test_get_cached_capsule_no_cache(self):
        """Test getting cached capsule when cache disabled."""
        state = ResilienceState()
        state.cache = None

        with patch("forge.resilience.integration.get_resilience_state", return_value=state):
            result = await get_cached_capsule("cap_123")

            assert result is None

    @pytest.mark.asyncio
    async def test_cache_capsule(self, mock_state):
        """Test caching capsule."""
        mock_state.cache.set.return_value = True

        with patch("forge.resilience.integration.get_resilience_state", return_value=mock_state):
            with patch("forge.resilience.integration.get_resilience_config") as mock_config:
                mock_config.return_value.cache.capsule_key_pattern = "forge:capsule:{capsule_id}"

                result = await cache_capsule("cap_123", {"id": "cap_123"})

                assert result is True

    @pytest.mark.asyncio
    async def test_invalidate_capsule_cache(self, mock_state):
        """Test invalidating capsule cache."""
        with patch("forge.resilience.integration.get_resilience_state", return_value=mock_state):
            result = await invalidate_capsule_cache("cap_123")

            assert result == 1
            mock_state.invalidator.on_capsule_updated.assert_called_once_with("cap_123")

    @pytest.mark.asyncio
    async def test_get_cached_search(self, mock_state):
        """Test getting cached search results."""
        mock_state.cache.get.return_value = [{"id": "cap_1"}, {"id": "cap_2"}]

        with patch("forge.resilience.integration.get_resilience_state", return_value=mock_state):
            with patch("forge.resilience.integration.get_resilience_config") as mock_config:
                mock_config.return_value.cache.search_key_pattern = "forge:search:{query_hash}"

                result = await get_cached_search("hash123")

                assert len(result) == 2

    @pytest.mark.asyncio
    async def test_cache_search_results(self, mock_state):
        """Test caching search results."""
        mock_state.cache.set.return_value = True

        with patch("forge.resilience.integration.get_resilience_state", return_value=mock_state):
            with patch("forge.resilience.integration.get_resilience_config") as mock_config:
                mock_config.return_value.cache.search_key_pattern = "forge:search:{query_hash}"

                results = [{"id": "cap_1"}, {"id": "cap_2"}]
                result = await cache_search_results("hash123", results)

                assert result is True

    @pytest.mark.asyncio
    async def test_get_cached_lineage(self, mock_state):
        """Test getting cached lineage."""
        mock_state.cache.get.return_value = {"ancestors": [], "descendants": []}

        with patch("forge.resilience.integration.get_resilience_state", return_value=mock_state):
            with patch("forge.resilience.integration.get_resilience_config") as mock_config:
                mock_config.return_value.cache.lineage_key_pattern = "forge:lineage:{capsule_id}:{depth}"

                result = await get_cached_lineage("cap_123", 5)

                assert "ancestors" in result

    @pytest.mark.asyncio
    async def test_cache_lineage(self, mock_state):
        """Test caching lineage."""
        mock_state.cache.set.return_value = True

        with patch("forge.resilience.integration.get_resilience_state", return_value=mock_state):
            with patch("forge.resilience.integration.get_resilience_config") as mock_config:
                mock_config.return_value.cache.lineage_key_pattern = "forge:lineage:{capsule_id}:{depth}"

                lineage_data = {
                    "ancestors": [{"id": "cap_parent"}],
                    "descendants": [{"id": "cap_child"}],
                }
                result = await cache_lineage("cap_123", 5, lineage_data)

                assert result is True


class TestContentValidationHelpers:
    """Tests for content validation helper functions."""

    @pytest.mark.asyncio
    async def test_validate_capsule_content(self):
        """Test validating capsule content."""
        mock_validator = MagicMock()
        mock_validator.validate = AsyncMock(
            return_value=ValidationResult(valid=True, threat_level=ThreatLevel.NONE)
        )

        state = ResilienceState()
        state.validator = mock_validator

        with patch("forge.resilience.integration.get_resilience_state", return_value=state):
            result = await validate_capsule_content("Clean content")

            assert result.valid is True

    @pytest.mark.asyncio
    async def test_validate_capsule_content_no_validator(self):
        """Test validation when validator disabled."""
        state = ResilienceState()
        state.validator = None

        with patch("forge.resilience.integration.get_resilience_state", return_value=state):
            result = await validate_capsule_content("Any content")

            assert result.valid is True
            assert result.threat_level == ThreatLevel.NONE

    def test_check_content_validation_valid(self):
        """Test content validation check with valid result."""
        result = ValidationResult(valid=True, threat_level=ThreatLevel.NONE)

        # Should not raise
        check_content_validation(result)

    def test_check_content_validation_invalid(self):
        """Test content validation check with invalid result."""
        from fastapi import HTTPException

        result = ValidationResult(valid=False, threat_level=ThreatLevel.HIGH)

        with pytest.raises(HTTPException) as exc_info:
            check_content_validation(result)

        assert exc_info.value.status_code == 400


class TestMetricsHelpers:
    """Tests for metrics helper functions."""

    def test_record_capsule_created(self):
        """Test recording capsule creation."""
        mock_metrics = MagicMock()

        with patch("forge.resilience.integration.get_metrics", return_value=mock_metrics):
            record_capsule_created("KNOWLEDGE")

            mock_metrics.capsule_created.assert_called_once_with("KNOWLEDGE")

    def test_record_capsule_updated(self):
        """Test recording capsule update."""
        mock_metrics = MagicMock()

        with patch("forge.resilience.integration.get_metrics", return_value=mock_metrics):
            record_capsule_updated("DECISION")

            mock_metrics.capsule_updated.assert_called_once_with("DECISION")

    def test_record_capsule_deleted(self):
        """Test recording capsule deletion."""
        mock_metrics = MagicMock()

        with patch("forge.resilience.integration.get_metrics", return_value=mock_metrics):
            record_capsule_deleted("MEMORY")

            mock_metrics.capsule_deleted.assert_called_once_with("MEMORY")

    def test_record_search(self):
        """Test recording search metrics."""
        mock_metrics = MagicMock()

        with patch("forge.resilience.integration.get_metrics", return_value=mock_metrics):
            record_search(0.5, 25)

            mock_metrics.search_latency.assert_called_once_with(0.5, 25)

    def test_record_lineage_query(self):
        """Test recording lineage query metrics."""
        mock_metrics = MagicMock()

        with patch("forge.resilience.integration.get_metrics", return_value=mock_metrics):
            record_lineage_query(0.3, 5)

            mock_metrics.lineage_query_latency.assert_called_once_with(0.3, 5)

    def test_record_cache_hit(self):
        """Test recording cache hit."""
        mock_metrics = MagicMock()

        with patch("forge.resilience.integration.get_metrics", return_value=mock_metrics):
            record_cache_hit("lineage")

            mock_metrics.cache_hit.assert_called_once_with("lineage")

    def test_record_cache_miss(self):
        """Test recording cache miss."""
        mock_metrics = MagicMock()

        with patch("forge.resilience.integration.get_metrics", return_value=mock_metrics):
            record_cache_miss("search")

            mock_metrics.cache_miss.assert_called_once_with("search")


class TestGovernanceCachingHelpers:
    """Tests for governance caching helper functions."""

    @pytest.fixture
    def mock_state(self):
        """Create mock resilience state."""
        state = ResilienceState()
        state.cache = AsyncMock()
        state.initialized = True
        return state

    @pytest.mark.asyncio
    async def test_get_cached_proposal(self, mock_state):
        """Test getting cached proposal."""
        mock_state.cache.get.return_value = {"id": "prop_123", "title": "Test"}

        with patch("forge.resilience.integration.get_resilience_state", return_value=mock_state):
            result = await get_cached_proposal("prop_123")

            assert result["id"] == "prop_123"

    @pytest.mark.asyncio
    async def test_cache_proposal(self, mock_state):
        """Test caching proposal."""
        mock_state.cache.set.return_value = True

        with patch("forge.resilience.integration.get_resilience_state", return_value=mock_state):
            result = await cache_proposal("prop_123", {"id": "prop_123"})

            assert result is True

    @pytest.mark.asyncio
    async def test_invalidate_proposal_cache(self, mock_state):
        """Test invalidating proposal cache."""
        with patch("forge.resilience.integration.get_resilience_state", return_value=mock_state):
            result = await invalidate_proposal_cache("prop_123")

            assert result == 1
            assert mock_state.cache.delete.call_count >= 1

    @pytest.mark.asyncio
    async def test_get_cached_proposals_list(self, mock_state):
        """Test getting cached proposals list."""
        mock_state.cache.get.return_value = {"proposals": [], "total": 0}

        with patch("forge.resilience.integration.get_resilience_state", return_value=mock_state):
            result = await get_cached_proposals_list("status:active")

            assert "proposals" in result

    @pytest.mark.asyncio
    async def test_cache_proposals_list(self, mock_state):
        """Test caching proposals list."""
        mock_state.cache.set.return_value = True

        with patch("forge.resilience.integration.get_resilience_state", return_value=mock_state):
            data = {"proposals": [], "total": 0}
            result = await cache_proposals_list("status:active", data)

            assert result is True

    @pytest.mark.asyncio
    async def test_get_cached_governance_metrics(self, mock_state):
        """Test getting cached governance metrics."""
        mock_state.cache.get.return_value = {"active_proposals": 5}

        with patch("forge.resilience.integration.get_resilience_state", return_value=mock_state):
            result = await get_cached_governance_metrics()

            assert result["active_proposals"] == 5

    @pytest.mark.asyncio
    async def test_cache_governance_metrics(self, mock_state):
        """Test caching governance metrics."""
        mock_state.cache.set.return_value = True

        with patch("forge.resilience.integration.get_resilience_state", return_value=mock_state):
            result = await cache_governance_metrics({"active_proposals": 5})

            assert result is True


class TestGovernanceMetricsHelpers:
    """Tests for governance metrics helper functions."""

    def test_record_proposal_created(self):
        """Test recording proposal creation."""
        mock_metrics = MagicMock()

        with patch("forge.resilience.integration.get_metrics", return_value=mock_metrics):
            record_proposal_created("STANDARD")

            mock_metrics.increment.assert_called_once()

    def test_record_vote_cast(self):
        """Test recording vote cast."""
        mock_metrics = MagicMock()

        with patch("forge.resilience.integration.get_metrics", return_value=mock_metrics):
            record_vote_cast("approve")

            mock_metrics.increment.assert_called_once()

    def test_record_login_attempt(self):
        """Test recording login attempt."""
        mock_metrics = MagicMock()

        with patch("forge.resilience.integration.get_metrics", return_value=mock_metrics):
            record_login_attempt(True)

            mock_metrics.increment.assert_called_once()


class TestOverlayCachingHelpers:
    """Tests for overlay caching helper functions."""

    @pytest.fixture
    def mock_state(self):
        """Create mock resilience state."""
        state = ResilienceState()
        state.cache = AsyncMock()
        state.initialized = True
        return state

    @pytest.mark.asyncio
    async def test_get_cached_overlay_list(self, mock_state):
        """Test getting cached overlay list."""
        mock_state.cache.get.return_value = [{"id": "overlay_1"}]

        with patch("forge.resilience.integration.get_resilience_state", return_value=mock_state):
            result = await get_cached_overlay_list()

            assert len(result) == 1

    @pytest.mark.asyncio
    async def test_cache_overlay_list(self, mock_state):
        """Test caching overlay list."""
        mock_state.cache.set.return_value = True

        with patch("forge.resilience.integration.get_resilience_state", return_value=mock_state):
            result = await cache_overlay_list([{"id": "overlay_1"}])

            assert result is True

    @pytest.mark.asyncio
    async def test_invalidate_overlay_cache(self, mock_state):
        """Test invalidating overlay cache."""
        with patch("forge.resilience.integration.get_resilience_state", return_value=mock_state):
            result = await invalidate_overlay_cache()

            assert result == 1


class TestSystemCachingHelpers:
    """Tests for system caching helper functions."""

    @pytest.fixture
    def mock_state(self):
        """Create mock resilience state."""
        state = ResilienceState()
        state.cache = AsyncMock()
        state.initialized = True
        return state

    @pytest.mark.asyncio
    async def test_get_cached_system_metrics(self, mock_state):
        """Test getting cached system metrics."""
        mock_state.cache.get.return_value = {"cpu": 50, "memory": 60}

        with patch("forge.resilience.integration.get_resilience_state", return_value=mock_state):
            result = await get_cached_system_metrics()

            assert result["cpu"] == 50

    @pytest.mark.asyncio
    async def test_cache_system_metrics(self, mock_state):
        """Test caching system metrics."""
        mock_state.cache.set.return_value = True

        with patch("forge.resilience.integration.get_resilience_state", return_value=mock_state):
            result = await cache_system_metrics({"cpu": 50})

            assert result is True

    @pytest.mark.asyncio
    async def test_get_cached_health_status(self, mock_state):
        """Test getting cached health status."""
        mock_state.cache.get.return_value = {"status": "healthy"}

        with patch("forge.resilience.integration.get_resilience_state", return_value=mock_state):
            result = await get_cached_health_status()

            assert result["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_cache_health_status(self, mock_state):
        """Test caching health status."""
        mock_state.cache.set.return_value = True

        with patch("forge.resilience.integration.get_resilience_state", return_value=mock_state):
            result = await cache_health_status({"status": "healthy"})

            assert result is True


class TestGlobalFunctions:
    """Tests for module-level functions."""

    @pytest.mark.asyncio
    async def test_get_resilience_state(self):
        """Test getting global resilience state."""
        with patch("forge.resilience.integration._resilience_state", None):
            with patch("forge.resilience.integration.get_resilience_config") as mock_config:
                mock_config.return_value.cache.enabled = False
                mock_config.return_value.content_validation.enabled = False
                mock_config.return_value.observability.enabled = False

                state = await get_resilience_state()

                assert isinstance(state, ResilienceState)
                assert state.initialized is True

    @pytest.mark.asyncio
    async def test_initialize_resilience(self):
        """Test initializing resilience for FastAPI app."""
        app = MagicMock()
        app.state = MagicMock()

        with patch("forge.resilience.integration._resilience_state", None):
            with patch("forge.resilience.integration.get_resilience_config") as mock_config:
                mock_config.return_value.cache.enabled = False
                mock_config.return_value.content_validation.enabled = False
                mock_config.return_value.observability.enabled = False

                await initialize_resilience(app)

                assert hasattr(app.state, "resilience")

    @pytest.mark.asyncio
    async def test_shutdown_resilience(self):
        """Test shutting down resilience."""
        app = MagicMock()
        app.state.resilience = AsyncMock()

        await shutdown_resilience(app)

        app.state.resilience.close.assert_called_once()
