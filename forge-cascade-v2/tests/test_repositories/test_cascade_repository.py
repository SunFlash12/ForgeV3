"""
Cascade Repository Tests for Forge Cascade V2

Comprehensive tests for the CascadeRepository including:
- CascadeChain CRUD operations
- CascadeEvent management
- Chain lifecycle (create, update, complete)
- Serialization/deserialization
- Cleanup and metrics
"""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from forge.database.client import Neo4jClient
from forge.models.events import CascadeChain, CascadeEvent
from forge.repositories.base import QueryTimeoutConfig
from forge.repositories.cascade_repository import (
    CascadeRepository,
    get_cascade_repository,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_db_client():
    """Create mock database client."""
    client = AsyncMock(spec=Neo4jClient)
    client.execute = AsyncMock(return_value=[])
    client.execute_single = AsyncMock(return_value=None)
    return client


@pytest.fixture
def cascade_repository(mock_db_client):
    """Create CascadeRepository with mock client."""
    return CascadeRepository(mock_db_client)


@pytest.fixture
def sample_cascade_event():
    """Create a sample CascadeEvent."""
    return CascadeEvent(
        id="event-123",
        source_overlay="overlay-001",
        insight_type="anomaly_detected",
        insight_data={"anomaly_score": 0.95, "affected_entities": ["cap-1", "cap-2"]},
        hop_count=1,
        max_hops=5,
        visited_overlays=["overlay-001"],
        impact_score=0.8,
        timestamp=datetime.now(UTC),
        correlation_id="corr-123",
    )


@pytest.fixture
def sample_cascade_chain(sample_cascade_event):
    """Create a sample CascadeChain."""
    return CascadeChain(
        cascade_id="cascade-123",
        initiated_by="overlay-001",
        initiated_at=datetime.now(UTC),
        events=[sample_cascade_event],
        total_hops=1,
        overlays_affected=["overlay-001"],
        insights_generated=1,
        actions_triggered=0,
        errors_encountered=0,
    )


@pytest.fixture
def sample_chain_node_data():
    """Sample chain node data from Neo4j."""
    return {
        "cascade_id": "cascade-123",
        "initiated_by": "overlay-001",
        "initiated_at": datetime.now(UTC).isoformat(),
        "total_hops": 3,
        "overlays_affected": ["overlay-001", "overlay-002", "overlay-003"],
        "insights_generated": 5,
        "actions_triggered": 2,
        "errors_encountered": 0,
        "status": "active",
        "completed_at": None,
    }


@pytest.fixture
def sample_event_node_data():
    """Sample event node data from Neo4j."""
    return {
        "id": "event-123",
        "source_overlay": "overlay-001",
        "insight_type": "anomaly_detected",
        "insight_data": json.dumps({"anomaly_score": 0.95}),
        "hop_count": 1,
        "max_hops": 5,
        "visited_overlays": ["overlay-001"],
        "impact_score": 0.8,
        "timestamp": datetime.now(UTC).isoformat(),
        "correlation_id": "corr-123",
    }


# =============================================================================
# Repository Initialization Tests
# =============================================================================


class TestCascadeRepositoryInit:
    """Tests for CascadeRepository initialization."""

    def test_init_with_default_timeout(self, mock_db_client):
        """Repository initializes with default timeout config."""
        repo = CascadeRepository(mock_db_client)

        assert repo.client == mock_db_client
        assert repo.timeout_config is not None

    def test_init_with_custom_timeout(self, mock_db_client):
        """Repository initializes with custom timeout config."""
        custom_config = QueryTimeoutConfig(read_timeout=10.0, write_timeout=30.0)
        repo = CascadeRepository(mock_db_client, timeout_config=custom_config)

        assert repo.timeout_config.read_timeout == 10.0
        assert repo.timeout_config.write_timeout == 30.0


# =============================================================================
# Helper Method Tests
# =============================================================================


class TestHelperMethods:
    """Tests for repository helper methods."""

    def test_generate_id(self, cascade_repository):
        """_generate_id returns unique UUID strings."""
        id1 = cascade_repository._generate_id()
        id2 = cascade_repository._generate_id()

        assert id1 != id2
        assert isinstance(id1, str)

    def test_now_returns_utc(self, cascade_repository):
        """_now returns UTC datetime."""
        now = cascade_repository._now()

        assert isinstance(now, datetime)
        assert now.tzinfo == UTC

    def test_serialize_event(self, cascade_repository, sample_cascade_event):
        """_serialize_event converts event to dict."""
        result = cascade_repository._serialize_event(sample_cascade_event)

        assert result["id"] == "event-123"
        assert result["source_overlay"] == "overlay-001"
        assert isinstance(result["insight_data"], str)
        assert json.loads(result["insight_data"]) == sample_cascade_event.insight_data

    def test_deserialize_event(self, cascade_repository, sample_event_node_data):
        """_deserialize_event converts dict to CascadeEvent."""
        result = cascade_repository._deserialize_event(sample_event_node_data)

        assert result is not None
        assert result.id == "event-123"
        assert result.source_overlay == "overlay-001"
        assert isinstance(result.insight_data, dict)

    def test_deserialize_event_empty(self, cascade_repository):
        """_deserialize_event returns None for empty data."""
        assert cascade_repository._deserialize_event({}) is None
        assert cascade_repository._deserialize_event(None) is None  # type: ignore

    def test_deserialize_event_handles_invalid_data(self, cascade_repository):
        """_deserialize_event handles invalid data gracefully."""
        invalid_data = {"invalid": "data"}
        result = cascade_repository._deserialize_event(invalid_data)

        assert result is None

    def test_deserialize_chain(
        self, cascade_repository, sample_chain_node_data, sample_event_node_data
    ):
        """_deserialize_chain converts dict to CascadeChain."""
        result = cascade_repository._deserialize_chain(
            sample_chain_node_data, [sample_event_node_data]
        )

        assert result is not None
        assert result.cascade_id == "cascade-123"
        assert len(result.events) == 1
        assert result.events[0].id == "event-123"

    def test_deserialize_chain_empty(self, cascade_repository):
        """_deserialize_chain returns None for empty data."""
        assert cascade_repository._deserialize_chain({}) is None
        assert cascade_repository._deserialize_chain(None) is None  # type: ignore

    def test_deserialize_chain_without_events(
        self, cascade_repository, sample_chain_node_data
    ):
        """_deserialize_chain handles chain without events."""
        result = cascade_repository._deserialize_chain(sample_chain_node_data)

        assert result is not None
        assert result.cascade_id == "cascade-123"
        assert len(result.events) == 0


# =============================================================================
# Create Chain Tests
# =============================================================================


class TestCreateChain:
    """Tests for create_chain method."""

    @pytest.mark.asyncio
    async def test_create_chain_success(
        self, cascade_repository, mock_db_client, sample_cascade_chain
    ):
        """Create chain successfully."""
        mock_db_client.execute_single.return_value = {"chain": {"cascade_id": "cascade-123"}}

        result = await cascade_repository.create_chain(sample_cascade_chain)

        assert result.cascade_id == "cascade-123"
        # First call creates chain, subsequent calls add events
        assert mock_db_client.execute_single.call_count >= 1

    @pytest.mark.asyncio
    async def test_create_chain_creates_events(
        self, cascade_repository, mock_db_client, sample_cascade_chain
    ):
        """Create chain also creates associated events."""
        mock_db_client.execute_single.return_value = {"chain": {"cascade_id": "cascade-123"}}

        await cascade_repository.create_chain(sample_cascade_chain)

        # Should call execute_single for chain + each event
        # 1 for create_chain + 1 for add_event
        assert mock_db_client.execute_single.call_count == 2

    @pytest.mark.asyncio
    async def test_create_chain_uses_write_timeout(
        self, cascade_repository, mock_db_client, sample_cascade_chain
    ):
        """Create chain uses write timeout."""
        mock_db_client.execute_single.return_value = {"chain": {"cascade_id": "cascade-123"}}

        await cascade_repository.create_chain(sample_cascade_chain)

        first_call = mock_db_client.execute_single.call_args_list[0]
        assert first_call.kwargs.get("timeout") == cascade_repository.timeout_config.write_timeout


# =============================================================================
# Add Event Tests
# =============================================================================


class TestAddEvent:
    """Tests for add_event method."""

    @pytest.mark.asyncio
    async def test_add_event_success(
        self, cascade_repository, mock_db_client, sample_cascade_event
    ):
        """Add event to chain successfully."""
        mock_db_client.execute_single.return_value = {"event": {"id": "event-123"}}

        result = await cascade_repository.add_event("cascade-123", sample_cascade_event, order=0)

        assert result.id == "event-123"

    @pytest.mark.asyncio
    async def test_add_event_auto_calculates_order(
        self, cascade_repository, mock_db_client, sample_cascade_event
    ):
        """Add event auto-calculates order when not provided."""
        # First call returns count, second creates event
        mock_db_client.execute_single.side_effect = [
            {"count": 5},  # Existing event count
            {"event": {"id": "event-123"}},  # Created event
        ]

        await cascade_repository.add_event("cascade-123", sample_cascade_event)

        # Verify order calculation query was called
        first_call = mock_db_client.execute_single.call_args_list[0]
        query = first_call[0][0]
        assert "count(e)" in query

    @pytest.mark.asyncio
    async def test_add_event_increments_chain_counters(
        self, cascade_repository, mock_db_client, sample_cascade_event
    ):
        """Add event increments chain hop and insight counters."""
        mock_db_client.execute_single.return_value = {"event": {"id": "event-123"}}

        await cascade_repository.add_event("cascade-123", sample_cascade_event, order=0)

        call_args = mock_db_client.execute_single.call_args
        query = call_args[0][0]
        assert "total_hops + 1" in query
        assert "insights_generated + 1" in query


# =============================================================================
# Update Chain Tests
# =============================================================================


class TestUpdateChain:
    """Tests for update_chain method."""

    @pytest.mark.asyncio
    async def test_update_chain_success(
        self, cascade_repository, mock_db_client, sample_cascade_chain
    ):
        """Update chain successfully."""
        mock_db_client.execute_single.return_value = {
            "chain": {"cascade_id": "cascade-123"}
        }

        sample_cascade_chain.total_hops = 5
        sample_cascade_chain.insights_generated = 10
        result = await cascade_repository.update_chain(sample_cascade_chain)

        assert result.cascade_id == "cascade-123"

    @pytest.mark.asyncio
    async def test_update_chain_query_structure(
        self, cascade_repository, mock_db_client, sample_cascade_chain
    ):
        """Update chain uses correct query structure."""
        mock_db_client.execute_single.return_value = {
            "chain": {"cascade_id": "cascade-123"}
        }

        sample_cascade_chain.errors_encountered = 2
        await cascade_repository.update_chain(sample_cascade_chain)

        call_args = mock_db_client.execute_single.call_args
        query = call_args[0][0]
        params = call_args[0][1]
        assert "SET c.total_hops" in query
        assert params["errors_encountered"] == 2


# =============================================================================
# Complete Chain Tests
# =============================================================================


class TestCompleteChain:
    """Tests for complete_chain method."""

    @pytest.mark.asyncio
    async def test_complete_chain_success(
        self, cascade_repository, mock_db_client, sample_chain_node_data, sample_event_node_data
    ):
        """Complete chain successfully."""
        # First call sets completed_at, second fetches full chain
        completed_data = {**sample_chain_node_data, "completed_at": datetime.now(UTC).isoformat()}
        mock_db_client.execute_single.side_effect = [
            {"chain": completed_data},  # complete_chain SET
            {"chain": completed_data, "events": [sample_event_node_data]},  # get_by_id
        ]

        result = await cascade_repository.complete_chain("cascade-123")

        assert result is not None
        assert result.completed_at is not None

    @pytest.mark.asyncio
    async def test_complete_chain_not_found(self, cascade_repository, mock_db_client):
        """Complete chain returns None when not found."""
        mock_db_client.execute_single.return_value = None

        result = await cascade_repository.complete_chain("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_complete_chain_sets_status(
        self, cascade_repository, mock_db_client, sample_chain_node_data, sample_event_node_data
    ):
        """Complete chain sets status to completed."""
        completed_data = {**sample_chain_node_data, "status": "completed"}
        mock_db_client.execute_single.side_effect = [
            {"chain": completed_data},
            {"chain": completed_data, "events": []},
        ]

        await cascade_repository.complete_chain("cascade-123")

        call_args = mock_db_client.execute_single.call_args_list[0]
        query = call_args[0][0]
        assert "status = 'completed'" in query


# =============================================================================
# Get By ID Tests
# =============================================================================


class TestGetById:
    """Tests for get_by_id method."""

    @pytest.mark.asyncio
    async def test_get_by_id_found(
        self, cascade_repository, mock_db_client, sample_chain_node_data, sample_event_node_data
    ):
        """Get chain by ID when found."""
        mock_db_client.execute_single.return_value = {
            "chain": sample_chain_node_data,
            "events": [sample_event_node_data],
        }

        result = await cascade_repository.get_by_id("cascade-123")

        assert result is not None
        assert result.cascade_id == "cascade-123"
        assert len(result.events) == 1

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, cascade_repository, mock_db_client):
        """Get chain by ID returns None when not found."""
        mock_db_client.execute_single.return_value = None

        result = await cascade_repository.get_by_id("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_id_empty_chain(self, cascade_repository, mock_db_client):
        """Get chain by ID returns None when chain is empty."""
        mock_db_client.execute_single.return_value = {"chain": None}

        result = await cascade_repository.get_by_id("cascade-123")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_id_uses_read_timeout(self, cascade_repository, mock_db_client):
        """Get by ID uses read timeout."""
        mock_db_client.execute_single.return_value = None

        await cascade_repository.get_by_id("cascade-123")

        call_args = mock_db_client.execute_single.call_args
        assert call_args.kwargs.get("timeout") == cascade_repository.timeout_config.read_timeout


# =============================================================================
# Get Active Chains Tests
# =============================================================================


class TestGetActiveChains:
    """Tests for get_active_chains method."""

    @pytest.mark.asyncio
    async def test_get_active_chains(
        self, cascade_repository, mock_db_client, sample_chain_node_data, sample_event_node_data
    ):
        """Get active chains."""
        mock_db_client.execute.return_value = [
            {"chain": sample_chain_node_data, "events": [sample_event_node_data]},
            {"chain": {**sample_chain_node_data, "cascade_id": "cascade-456"}, "events": []},
        ]

        result = await cascade_repository.get_active_chains()

        assert len(result) == 2
        assert result[0].cascade_id == "cascade-123"

    @pytest.mark.asyncio
    async def test_get_active_chains_filters_by_status(
        self, cascade_repository, mock_db_client
    ):
        """Get active chains filters by status or completed_at."""
        mock_db_client.execute.return_value = []

        await cascade_repository.get_active_chains()

        call_args = mock_db_client.execute.call_args
        query = call_args[0][0]
        assert "status = 'active'" in query
        assert "completed_at IS NULL" in query

    @pytest.mark.asyncio
    async def test_get_active_chains_empty(self, cascade_repository, mock_db_client):
        """Get active chains returns empty list when none found."""
        mock_db_client.execute.return_value = []

        result = await cascade_repository.get_active_chains()

        assert result == []


# =============================================================================
# Get Completed Chains Tests
# =============================================================================


class TestGetCompletedChains:
    """Tests for get_completed_chains method."""

    @pytest.mark.asyncio
    async def test_get_completed_chains(
        self, cascade_repository, mock_db_client, sample_chain_node_data, sample_event_node_data
    ):
        """Get completed chains."""
        completed_data = {
            **sample_chain_node_data,
            "status": "completed",
            "completed_at": datetime.now(UTC).isoformat(),
        }
        mock_db_client.execute.return_value = [
            {"chain": completed_data, "events": [sample_event_node_data]}
        ]

        result = await cascade_repository.get_completed_chains()

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_completed_chains_with_pagination(
        self, cascade_repository, mock_db_client
    ):
        """Get completed chains respects pagination."""
        mock_db_client.execute.return_value = []

        await cascade_repository.get_completed_chains(limit=50, skip=10)

        call_args = mock_db_client.execute.call_args
        params = call_args[0][1]
        assert params["limit"] == 50
        assert params["skip"] == 10

    @pytest.mark.asyncio
    async def test_get_completed_chains_caps_limit(self, cascade_repository, mock_db_client):
        """Get completed chains caps limit at 500."""
        mock_db_client.execute.return_value = []

        await cascade_repository.get_completed_chains(limit=1000)

        call_args = mock_db_client.execute.call_args
        params = call_args[0][1]
        assert params["limit"] == 500

    @pytest.mark.asyncio
    async def test_get_completed_chains_enforces_non_negative_skip(
        self, cascade_repository, mock_db_client
    ):
        """Get completed chains enforces non-negative skip."""
        mock_db_client.execute.return_value = []

        await cascade_repository.get_completed_chains(skip=-10)

        call_args = mock_db_client.execute.call_args
        params = call_args[0][1]
        assert params["skip"] == 0


# =============================================================================
# Delete Chain Tests
# =============================================================================


class TestDeleteChain:
    """Tests for delete_chain method."""

    @pytest.mark.asyncio
    async def test_delete_chain_success(self, cascade_repository, mock_db_client):
        """Delete chain successfully."""
        mock_db_client.execute_single.return_value = {"deleted": 1}

        result = await cascade_repository.delete_chain("cascade-123")

        assert result is True

    @pytest.mark.asyncio
    async def test_delete_chain_not_found(self, cascade_repository, mock_db_client):
        """Delete chain returns False when not found."""
        mock_db_client.execute_single.return_value = {"deleted": 0}

        result = await cascade_repository.delete_chain("nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_delete_chain_uses_detach_delete(self, cascade_repository, mock_db_client):
        """Delete chain uses DETACH DELETE for relationships."""
        mock_db_client.execute_single.return_value = {"deleted": 1}

        await cascade_repository.delete_chain("cascade-123")

        call_args = mock_db_client.execute_single.call_args
        query = call_args[0][0]
        assert "DETACH DELETE" in query

    @pytest.mark.asyncio
    async def test_delete_chain_deletes_events(self, cascade_repository, mock_db_client):
        """Delete chain also deletes associated events."""
        mock_db_client.execute_single.return_value = {"deleted": 1}

        await cascade_repository.delete_chain("cascade-123")

        call_args = mock_db_client.execute_single.call_args
        query = call_args[0][0]
        assert "CascadeEvent" in query


# =============================================================================
# Cleanup Old Chains Tests
# =============================================================================


class TestCleanupOldChains:
    """Tests for cleanup_old_chains method."""

    @pytest.mark.asyncio
    async def test_cleanup_old_chains(self, cascade_repository, mock_db_client):
        """Cleanup old chains."""
        mock_db_client.execute_single.return_value = {"deleted": 10}

        result = await cascade_repository.cleanup_old_chains(days_old=30)

        assert result == 10

    @pytest.mark.asyncio
    async def test_cleanup_clamps_days_old_minimum(self, cascade_repository, mock_db_client):
        """Cleanup clamps days_old to minimum of 1."""
        mock_db_client.execute_single.return_value = {"deleted": 0}

        await cascade_repository.cleanup_old_chains(days_old=0)

        call_args = mock_db_client.execute_single.call_args
        params = call_args[0][1]
        assert params["days_old"] == 1

    @pytest.mark.asyncio
    async def test_cleanup_clamps_days_old_maximum(self, cascade_repository, mock_db_client):
        """Cleanup clamps days_old to maximum of 365."""
        mock_db_client.execute_single.return_value = {"deleted": 0}

        await cascade_repository.cleanup_old_chains(days_old=1000)

        call_args = mock_db_client.execute_single.call_args
        params = call_args[0][1]
        assert params["days_old"] == 365

    @pytest.mark.asyncio
    async def test_cleanup_only_completed_chains(self, cascade_repository, mock_db_client):
        """Cleanup only affects completed chains."""
        mock_db_client.execute_single.return_value = {"deleted": 5}

        await cascade_repository.cleanup_old_chains(days_old=30)

        call_args = mock_db_client.execute_single.call_args
        query = call_args[0][0]
        assert "status = 'completed'" in query

    @pytest.mark.asyncio
    async def test_cleanup_returns_zero_on_none(self, cascade_repository, mock_db_client):
        """Cleanup returns 0 when result is None."""
        mock_db_client.execute_single.return_value = None

        result = await cascade_repository.cleanup_old_chains(days_old=30)

        assert result == 0


# =============================================================================
# Get Metrics Tests
# =============================================================================


class TestGetMetrics:
    """Tests for get_metrics method."""

    @pytest.mark.asyncio
    async def test_get_metrics(self, cascade_repository, mock_db_client):
        """Get metrics."""
        mock_db_client.execute_single.return_value = {
            "total_chains": 100,
            "active_chains": 10,
            "completed_chains": 90,
            "total_hops": 500,
            "avg_hops_per_chain": 5.0,
            "total_insights": 250,
            "total_errors": 5,
        }

        result = await cascade_repository.get_metrics()

        assert result["total_chains"] == 100
        assert result["active_chains"] == 10
        assert result["avg_hops_per_chain"] == 5.0

    @pytest.mark.asyncio
    async def test_get_metrics_defaults_on_none(self, cascade_repository, mock_db_client):
        """Get metrics returns defaults when result is None."""
        mock_db_client.execute_single.return_value = None

        result = await cascade_repository.get_metrics()

        assert result["total_chains"] == 0
        assert result["active_chains"] == 0
        assert result["avg_hops_per_chain"] == 0.0

    @pytest.mark.asyncio
    async def test_get_metrics_handles_null_avg(self, cascade_repository, mock_db_client):
        """Get metrics handles null average."""
        mock_db_client.execute_single.return_value = {
            "total_chains": 0,
            "active_chains": 0,
            "completed_chains": 0,
            "total_hops": 0,
            "avg_hops_per_chain": None,  # NULL when no chains
            "total_insights": 0,
            "total_errors": 0,
        }

        result = await cascade_repository.get_metrics()

        assert result["avg_hops_per_chain"] == 0.0


# =============================================================================
# Serialization Edge Cases Tests
# =============================================================================


class TestSerializationEdgeCases:
    """Tests for edge cases in serialization/deserialization."""

    def test_serialize_event_with_none_timestamp(self, cascade_repository):
        """Serialize event with None timestamp."""
        event = CascadeEvent(
            id="event-123",
            source_overlay="overlay-001",
            insight_type="test",
            insight_data={},
            timestamp=None,  # type: ignore
        )

        result = cascade_repository._serialize_event(event)

        assert result["timestamp"] is None

    def test_deserialize_event_with_dict_insight_data(
        self, cascade_repository, sample_event_node_data
    ):
        """Deserialize event when insight_data is already a dict."""
        sample_event_node_data["insight_data"] = {"already": "parsed"}

        result = cascade_repository._deserialize_event(sample_event_node_data)

        assert result is not None
        assert result.insight_data == {"already": "parsed"}

    def test_deserialize_chain_with_string_datetime(
        self, cascade_repository, sample_chain_node_data
    ):
        """Deserialize chain with ISO format datetime strings."""
        result = cascade_repository._deserialize_chain(sample_chain_node_data)

        assert result is not None
        assert isinstance(result.initiated_at, datetime)

    def test_deserialize_chain_with_datetime_object(
        self, cascade_repository, sample_chain_node_data
    ):
        """Deserialize chain when datetime is already an object."""
        sample_chain_node_data["initiated_at"] = datetime.now(UTC)
        sample_chain_node_data["completed_at"] = datetime.now(UTC)

        result = cascade_repository._deserialize_chain(sample_chain_node_data)

        assert result is not None
        assert isinstance(result.initiated_at, datetime)
        assert isinstance(result.completed_at, datetime)


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestFactoryFunction:
    """Tests for get_cascade_repository factory function."""

    def test_get_cascade_repository_creates_instance(self, mock_db_client):
        """get_cascade_repository creates repository instance."""
        import forge.repositories.cascade_repository as cascade_module

        cascade_module._cascade_repo = None

        repo = get_cascade_repository(mock_db_client)

        assert isinstance(repo, CascadeRepository)

    def test_get_cascade_repository_returns_singleton(self, mock_db_client):
        """get_cascade_repository returns same instance on subsequent calls."""
        import forge.repositories.cascade_repository as cascade_module

        cascade_module._cascade_repo = None

        repo1 = get_cascade_repository(mock_db_client)
        repo2 = get_cascade_repository()

        assert repo1 is repo2

    def test_get_cascade_repository_requires_client_first_call(self):
        """get_cascade_repository raises error without client on first call."""
        import forge.repositories.cascade_repository as cascade_module

        cascade_module._cascade_repo = None

        with pytest.raises(ValueError, match="Neo4j client required"):
            get_cascade_repository(None)


# =============================================================================
# Integration-like Tests
# =============================================================================


class TestChainLifecycle:
    """Tests for complete chain lifecycle."""

    @pytest.mark.asyncio
    async def test_full_chain_lifecycle(
        self,
        cascade_repository,
        mock_db_client,
        sample_cascade_chain,
        sample_chain_node_data,
        sample_event_node_data,
    ):
        """Test full chain lifecycle: create -> add events -> update -> complete."""
        # Setup mocks for full lifecycle
        mock_db_client.execute_single.side_effect = [
            # create_chain
            {"chain": sample_chain_node_data},
            # add_event (for initial event)
            {"event": sample_event_node_data},
            # add_event (new event)
            {"count": 1},
            {"event": {**sample_event_node_data, "id": "event-456"}},
            # update_chain
            {"chain": sample_chain_node_data},
            # complete_chain
            {
                "chain": {
                    **sample_chain_node_data,
                    "status": "completed",
                    "completed_at": datetime.now(UTC).isoformat(),
                }
            },
            # get_by_id (called by complete_chain)
            {
                "chain": {
                    **sample_chain_node_data,
                    "completed_at": datetime.now(UTC).isoformat(),
                },
                "events": [sample_event_node_data],
            },
        ]

        # Create chain
        chain = await cascade_repository.create_chain(sample_cascade_chain)
        assert chain.cascade_id == "cascade-123"

        # Add new event
        new_event = CascadeEvent(
            id="event-456",
            source_overlay="overlay-002",
            insight_type="pattern_found",
            insight_data={"pattern": "test"},
        )
        event = await cascade_repository.add_event("cascade-123", new_event)
        assert event.id == "event-456"

        # Update chain
        chain.total_hops = 2
        updated = await cascade_repository.update_chain(chain)
        assert updated is not None

        # Complete chain
        completed = await cascade_repository.complete_chain("cascade-123")
        assert completed is not None
        assert completed.completed_at is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
