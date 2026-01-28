"""
Tests for Revenue Repository.

This module tests the persistent storage for RevenueRecord models in Neo4j.
"""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from forge.virtuals.models.base import RevenueRecord, RevenueType
from forge.virtuals.revenue.repository import (
    RevenueRepository,
    get_revenue_repository,
)


# ==================== Fixtures ====================


@pytest.fixture
def mock_neo4j_client():
    """Create a mock Neo4j client."""
    client = MagicMock()
    client.execute_write = AsyncMock()
    client.execute_read = AsyncMock()
    return client


@pytest.fixture
def revenue_repo(mock_neo4j_client):
    """Create a RevenueRepository with mock client."""
    return RevenueRepository(mock_neo4j_client)


@pytest.fixture
def sample_revenue_record():
    """Create a sample revenue record."""
    return RevenueRecord(
        id="rev-123",
        timestamp=datetime.now(UTC),
        revenue_type=RevenueType.INFERENCE_FEE,
        amount_virtual=0.01,
        source_entity_id="capsule-456",
        source_entity_type="capsule",
        beneficiary_addresses=["0x" + "1" * 40],
    )


# ==================== Initialization Tests ====================


class TestRevenueRepositoryInit:
    """Tests for RevenueRepository initialization."""

    def test_repository_creation(self, mock_neo4j_client):
        """Test creating a repository."""
        repo = RevenueRepository(mock_neo4j_client)

        assert repo.client == mock_neo4j_client
        assert repo.logger is not None


# ==================== Create Tests ====================


class TestRevenueRepositoryCreate:
    """Tests for create method."""

    @pytest.mark.asyncio
    async def test_create_success(self, revenue_repo, sample_revenue_record, mock_neo4j_client):
        """Test successful record creation."""
        mock_neo4j_client.execute_write = AsyncMock(return_value=None)

        result = await revenue_repo.create(sample_revenue_record)

        assert result == sample_revenue_record
        mock_neo4j_client.execute_write.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_with_metadata(self, revenue_repo, mock_neo4j_client):
        """Test creating record with metadata."""
        record = RevenueRecord(
            id="rev-456",
            revenue_type=RevenueType.SERVICE_FEE,
            amount_virtual=1.0,
            source_entity_id="overlay-123",
            source_entity_type="overlay",
            metadata={"service_type": "analysis", "client": "user-789"},
        )

        mock_neo4j_client.execute_write = AsyncMock(return_value=None)

        result = await revenue_repo.create(record)

        assert result.id == "rev-456"

    @pytest.mark.asyncio
    async def test_create_connection_error(self, revenue_repo, sample_revenue_record, mock_neo4j_client):
        """Test handling connection error on create."""
        mock_neo4j_client.execute_write = AsyncMock(side_effect=ConnectionError("DB connection failed"))

        with pytest.raises(ConnectionError):
            await revenue_repo.create(sample_revenue_record)


# ==================== Update Tests ====================


class TestRevenueRepositoryUpdate:
    """Tests for update method."""

    @pytest.mark.asyncio
    async def test_update_success(self, revenue_repo, sample_revenue_record, mock_neo4j_client):
        """Test successful record update."""
        sample_revenue_record.distribution_complete = True
        sample_revenue_record.tx_hash = "0x" + "a" * 64

        mock_neo4j_client.execute_write = AsyncMock(return_value=None)

        result = await revenue_repo.update(sample_revenue_record)

        assert result == sample_revenue_record
        mock_neo4j_client.execute_write.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_timeout_error(self, revenue_repo, sample_revenue_record, mock_neo4j_client):
        """Test handling timeout error on update."""
        mock_neo4j_client.execute_write = AsyncMock(side_effect=TimeoutError("Query timeout"))

        with pytest.raises(TimeoutError):
            await revenue_repo.update(sample_revenue_record)


# ==================== Get By ID Tests ====================


class TestRevenueRepositoryGetById:
    """Tests for get_by_id method."""

    @pytest.mark.asyncio
    async def test_get_by_id_found(self, revenue_repo, mock_neo4j_client):
        """Test getting record by ID when found."""
        mock_record_data = {
            "id": "rev-123",
            "timestamp": datetime.now(UTC).isoformat(),
            "revenue_type": "inference_fee",
            "amount_virtual": 0.01,
            "source_entity_id": "capsule-456",
            "source_entity_type": "capsule",
            "beneficiary_addresses": ["0x" + "1" * 40],
            "distribution_complete": False,
        }

        mock_neo4j_client.execute_read = AsyncMock(return_value=[{"record": mock_record_data}])

        result = await revenue_repo.get_by_id("rev-123")

        assert result is not None
        assert result.id == "rev-123"
        assert result.revenue_type == RevenueType.INFERENCE_FEE

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, revenue_repo, mock_neo4j_client):
        """Test getting record by ID when not found."""
        mock_neo4j_client.execute_read = AsyncMock(return_value=[])

        result = await revenue_repo.get_by_id("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_id_connection_error(self, revenue_repo, mock_neo4j_client):
        """Test handling connection error on get_by_id."""
        mock_neo4j_client.execute_read = AsyncMock(side_effect=ConnectionError("DB error"))

        result = await revenue_repo.get_by_id("rev-123")

        # Should return None and log error
        assert result is None


# ==================== Query Pending Tests ====================


class TestRevenueRepositoryQueryPending:
    """Tests for query_pending method."""

    @pytest.mark.asyncio
    async def test_query_pending(self, revenue_repo, mock_neo4j_client):
        """Test querying pending records."""
        mock_records = [
            {
                "record": {
                    "id": "rev-1",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "revenue_type": "inference_fee",
                    "amount_virtual": 0.01,
                    "source_entity_id": "capsule-1",
                    "source_entity_type": "capsule",
                    "distribution_complete": False,
                }
            },
            {
                "record": {
                    "id": "rev-2",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "revenue_type": "service_fee",
                    "amount_virtual": 0.5,
                    "source_entity_id": "overlay-1",
                    "source_entity_type": "overlay",
                    "distribution_complete": False,
                }
            },
        ]

        mock_neo4j_client.execute_read = AsyncMock(return_value=mock_records)

        results = await revenue_repo.query_pending()

        assert len(results) == 2
        assert all(r.distribution_complete is False for r in results)


# ==================== Query Tests ====================


class TestRevenueRepositoryQuery:
    """Tests for query method."""

    @pytest.mark.asyncio
    async def test_query_no_filters(self, revenue_repo, mock_neo4j_client):
        """Test querying without filters."""
        mock_records = [
            {
                "record": {
                    "id": "rev-1",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "revenue_type": "inference_fee",
                    "amount_virtual": 0.01,
                    "source_entity_id": "capsule-1",
                    "source_entity_type": "capsule",
                }
            }
        ]

        mock_neo4j_client.execute_read = AsyncMock(return_value=mock_records)

        results = await revenue_repo.query()

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_query_by_entity_id(self, revenue_repo, mock_neo4j_client):
        """Test querying by entity ID."""
        mock_neo4j_client.execute_read = AsyncMock(return_value=[])

        await revenue_repo.query(entity_id="capsule-123")

        # Verify entity_id was included in query params
        call_args = mock_neo4j_client.execute_read.call_args
        assert call_args[1]["parameters"]["entity_id"] == "capsule-123"

    @pytest.mark.asyncio
    async def test_query_by_entity_type(self, revenue_repo, mock_neo4j_client):
        """Test querying by entity type."""
        mock_neo4j_client.execute_read = AsyncMock(return_value=[])

        await revenue_repo.query(entity_type="capsule")

        call_args = mock_neo4j_client.execute_read.call_args
        assert call_args[1]["parameters"]["entity_type"] == "capsule"

    @pytest.mark.asyncio
    async def test_query_by_date_range(self, revenue_repo, mock_neo4j_client):
        """Test querying by date range."""
        start = datetime.now(UTC) - timedelta(days=7)
        end = datetime.now(UTC)

        mock_neo4j_client.execute_read = AsyncMock(return_value=[])

        await revenue_repo.query(start_date=start, end_date=end)

        call_args = mock_neo4j_client.execute_read.call_args
        assert "start_date" in call_args[1]["parameters"]
        assert "end_date" in call_args[1]["parameters"]

    @pytest.mark.asyncio
    async def test_query_by_revenue_type(self, revenue_repo, mock_neo4j_client):
        """Test querying by revenue type."""
        mock_neo4j_client.execute_read = AsyncMock(return_value=[])

        await revenue_repo.query(revenue_type=RevenueType.TRADING_FEE)

        call_args = mock_neo4j_client.execute_read.call_args
        assert call_args[1]["parameters"]["revenue_type"] == "trading_fee"

    @pytest.mark.asyncio
    async def test_query_with_limit(self, revenue_repo, mock_neo4j_client):
        """Test querying with custom limit."""
        mock_neo4j_client.execute_read = AsyncMock(return_value=[])

        await revenue_repo.query(limit=50)

        call_args = mock_neo4j_client.execute_read.call_args
        assert call_args[1]["parameters"]["limit"] == 50

    @pytest.mark.asyncio
    async def test_query_connection_error(self, revenue_repo, mock_neo4j_client):
        """Test handling connection error on query."""
        mock_neo4j_client.execute_read = AsyncMock(side_effect=ConnectionError("DB error"))

        results = await revenue_repo.query()

        # Should return empty list and log error
        assert results == []


# ==================== Get Total By Entity Tests ====================


class TestRevenueRepositoryGetTotalByEntity:
    """Tests for get_total_by_entity method."""

    @pytest.mark.asyncio
    async def test_get_total_by_entity_success(self, revenue_repo, mock_neo4j_client):
        """Test getting total revenue by entity."""
        mock_neo4j_client.execute_read = AsyncMock(return_value=[{"total": 100.5}])

        total = await revenue_repo.get_total_by_entity("capsule-123", "capsule")

        assert total == 100.5

    @pytest.mark.asyncio
    async def test_get_total_by_entity_no_results(self, revenue_repo, mock_neo4j_client):
        """Test getting total when no records exist."""
        mock_neo4j_client.execute_read = AsyncMock(return_value=[{"total": None}])

        total = await revenue_repo.get_total_by_entity("nonexistent", "capsule")

        assert total == 0.0

    @pytest.mark.asyncio
    async def test_get_total_by_entity_error(self, revenue_repo, mock_neo4j_client):
        """Test handling error on get_total_by_entity."""
        mock_neo4j_client.execute_read = AsyncMock(side_effect=RuntimeError("Query failed"))

        total = await revenue_repo.get_total_by_entity("capsule-123", "capsule")

        assert total == 0.0


# ==================== Delete Tests ====================


class TestRevenueRepositoryDelete:
    """Tests for delete method."""

    @pytest.mark.asyncio
    async def test_delete_success(self, revenue_repo, mock_neo4j_client):
        """Test successful record deletion."""
        mock_neo4j_client.execute_write = AsyncMock(return_value=None)

        result = await revenue_repo.delete("rev-123")

        assert result is True

    @pytest.mark.asyncio
    async def test_delete_error(self, revenue_repo, mock_neo4j_client):
        """Test handling error on delete."""
        mock_neo4j_client.execute_write = AsyncMock(side_effect=RuntimeError("Delete failed"))

        result = await revenue_repo.delete("rev-123")

        assert result is False


# ==================== Deserialize Tests ====================


class TestRevenueRepositoryDeserialize:
    """Tests for _deserialize_record method."""

    def test_deserialize_complete_record(self, revenue_repo):
        """Test deserializing a complete record."""
        data = {
            "id": "rev-123",
            "timestamp": "2024-01-15T10:30:00+00:00",
            "revenue_type": "inference_fee",
            "amount_virtual": 0.01,
            "amount_usd": 0.05,
            "source_entity_id": "capsule-456",
            "source_entity_type": "capsule",
            "beneficiary_addresses": ["0x" + "1" * 40],
            "distribution_complete": True,
            "tx_hash": "0x" + "a" * 64,
            "metadata": "{}",
        }

        record = revenue_repo._deserialize_record(data)

        assert record is not None
        assert record.id == "rev-123"
        assert record.amount_virtual == 0.01
        assert record.distribution_complete is True

    def test_deserialize_empty_data(self, revenue_repo):
        """Test deserializing empty data."""
        result = revenue_repo._deserialize_record({})

        assert result is None

    def test_deserialize_none_data(self, revenue_repo):
        """Test deserializing None."""
        result = revenue_repo._deserialize_record(None)

        assert result is None

    def test_deserialize_timestamp_with_z(self, revenue_repo):
        """Test deserializing timestamp with Z suffix."""
        data = {
            "id": "rev-123",
            "timestamp": "2024-01-15T10:30:00Z",
            "revenue_type": "service_fee",
            "amount_virtual": 1.0,
            "source_entity_id": "overlay-123",
            "source_entity_type": "overlay",
        }

        record = revenue_repo._deserialize_record(data)

        assert record is not None
        assert record.timestamp is not None

    def test_deserialize_with_json_metadata(self, revenue_repo):
        """Test deserializing with JSON metadata string."""
        data = {
            "id": "rev-123",
            "timestamp": datetime.now(UTC).isoformat(),
            "revenue_type": "trading_fee",
            "amount_virtual": 0.5,
            "source_entity_id": "token-123",
            "source_entity_type": "agent_token",
            "metadata": '{"trade_type": "buy", "trader": "0x123"}',
        }

        record = revenue_repo._deserialize_record(data)

        assert record is not None

    def test_deserialize_invalid_revenue_type(self, revenue_repo):
        """Test deserializing with invalid revenue type."""
        data = {
            "id": "rev-123",
            "timestamp": datetime.now(UTC).isoformat(),
            "revenue_type": "invalid_type",
            "amount_virtual": 1.0,
            "source_entity_id": "entity-123",
            "source_entity_type": "capsule",
        }

        result = revenue_repo._deserialize_record(data)

        # Should return None due to invalid enum value
        assert result is None


# ==================== Global Repository Tests ====================


class TestGetRevenueRepository:
    """Tests for get_revenue_repository function."""

    def test_get_repository_first_call(self, mock_neo4j_client):
        """Test getting repository on first call."""
        import forge.virtuals.revenue.repository as repo_module

        repo_module._revenue_repo = None

        repo = get_revenue_repository(mock_neo4j_client)

        assert repo is not None
        assert isinstance(repo, RevenueRepository)

        # Cleanup
        repo_module._revenue_repo = None

    def test_get_repository_singleton(self, mock_neo4j_client):
        """Test repository is singleton."""
        import forge.virtuals.revenue.repository as repo_module

        repo_module._revenue_repo = None

        repo1 = get_revenue_repository(mock_neo4j_client)
        repo2 = get_revenue_repository()

        assert repo1 is repo2

        # Cleanup
        repo_module._revenue_repo = None

    def test_get_repository_without_client_on_first_call(self):
        """Test error when client not provided on first call."""
        import forge.virtuals.revenue.repository as repo_module

        repo_module._revenue_repo = None

        with pytest.raises(ValueError, match="Neo4j client required"):
            get_revenue_repository()

        # Cleanup
        repo_module._revenue_repo = None
