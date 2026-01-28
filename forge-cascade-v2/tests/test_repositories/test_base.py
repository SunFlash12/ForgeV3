"""
Base Repository Tests for Forge Cascade V2

Comprehensive tests for the BaseRepository abstract class including:
- CRUD operations (get_by_id, get_all, delete, exists)
- Field updates and queries
- Validation of identifiers
- Query timeout configuration
- Model conversion utilities
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from pydantic import BaseModel

from forge.database.client import Neo4jClient
from forge.repositories.base import (
    DEFAULT_QUERY_TIMEOUT,
    BaseRepository,
    QueryTimeoutConfig,
    validate_identifier,
)

# =============================================================================
# Test Models
# =============================================================================


class TestModel(BaseModel):
    """Test model for repository testing."""

    id: str
    name: str
    value: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TestCreateModel(BaseModel):
    """Test create schema."""

    name: str
    value: int = 0


class TestUpdateModel(BaseModel):
    """Test update schema."""

    name: str | None = None
    value: int | None = None


# =============================================================================
# Concrete Implementation for Testing
# =============================================================================


class ConcreteRepository(BaseRepository[TestModel, TestCreateModel, TestUpdateModel]):
    """Concrete implementation of BaseRepository for testing."""

    @property
    def node_label(self) -> str:
        return "TestNode"

    @property
    def model_class(self) -> type[TestModel]:
        return TestModel

    async def create(self, data: TestCreateModel, **kwargs: object) -> TestModel:
        """Create implementation for testing."""
        entity_id = self._generate_id()
        now = self._now()

        query = f"""
        CREATE (n:{self.node_label} {{
            id: $id,
            name: $name,
            value: $value,
            created_at: $created_at,
            updated_at: $updated_at
        }})
        RETURN n {{.*}} AS entity
        """

        params = {
            "id": entity_id,
            "name": data.name,
            "value": data.value,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }

        result = await self.client.execute_single(query, params)
        if result and result.get("entity"):
            return self._to_model(result["entity"])  # type: ignore
        raise RuntimeError("Failed to create entity")

    async def update(self, entity_id: str, data: TestUpdateModel) -> TestModel | None:
        """Update implementation for testing."""
        updates = []
        params = {"id": entity_id, "now": self._now().isoformat()}

        if data.name is not None:
            updates.append("n.name = $name")
            params["name"] = data.name
        if data.value is not None:
            updates.append("n.value = $value")
            params["value"] = data.value

        if not updates:
            return await self.get_by_id(entity_id)

        updates.append("n.updated_at = $now")
        set_clause = ", ".join(updates)

        query = f"""
        MATCH (n:{self.node_label} {{id: $id}})
        SET {set_clause}
        RETURN n {{.*}} AS entity
        """

        result = await self.client.execute_single(query, params)
        if result and result.get("entity"):
            return self._to_model(result["entity"])
        return None


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
def repository(mock_db_client):
    """Create repository with mock client."""
    return ConcreteRepository(mock_db_client)


@pytest.fixture
def sample_entity_data():
    """Sample entity data for testing."""
    return {
        "id": "test-id-123",
        "name": "Test Entity",
        "value": 42,
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
    }


# =============================================================================
# Identifier Validation Tests
# =============================================================================


class TestValidateIdentifier:
    """Tests for validate_identifier function."""

    def test_valid_identifier(self):
        """Valid identifiers pass validation."""
        assert validate_identifier("name") == "name"
        assert validate_identifier("user_id") == "user_id"
        assert validate_identifier("_private") == "_private"
        assert validate_identifier("camelCase") == "camelCase"
        assert validate_identifier("PascalCase") == "PascalCase"
        assert validate_identifier("test123") == "test123"

    def test_empty_identifier_raises(self):
        """Empty identifier raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_identifier("")

    def test_invalid_start_character_raises(self):
        """Identifier starting with number raises ValueError."""
        with pytest.raises(ValueError, match="Invalid"):
            validate_identifier("123abc")

    def test_special_characters_raise(self):
        """Identifier with special characters raises ValueError."""
        with pytest.raises(ValueError, match="Invalid"):
            validate_identifier("name-with-dash")
        with pytest.raises(ValueError, match="Invalid"):
            validate_identifier("name.with.dot")
        with pytest.raises(ValueError, match="Invalid"):
            validate_identifier("name with space")

    def test_sql_injection_attempt_raises(self):
        """SQL/Cypher injection attempts are rejected."""
        with pytest.raises(ValueError, match="Invalid"):
            validate_identifier("name; DROP TABLE users")
        with pytest.raises(ValueError, match="Invalid"):
            validate_identifier("name}] RETURN 1")

    def test_too_long_identifier_raises(self):
        """Identifier exceeding max length raises ValueError."""
        long_name = "a" * 65
        with pytest.raises(ValueError, match="too long"):
            validate_identifier(long_name)

    def test_max_length_identifier_valid(self):
        """Identifier at max length (64 chars) is valid."""
        max_name = "a" * 64
        assert validate_identifier(max_name) == max_name

    def test_custom_param_name_in_error(self):
        """Custom param name appears in error message."""
        with pytest.raises(ValueError, match="field_name"):
            validate_identifier("", "field_name")


# =============================================================================
# QueryTimeoutConfig Tests
# =============================================================================


class TestQueryTimeoutConfig:
    """Tests for QueryTimeoutConfig."""

    def test_default_values(self):
        """Default timeout values are set correctly."""
        config = QueryTimeoutConfig()
        assert config.read_timeout == 30.0
        assert config.write_timeout == 60.0
        assert config.complex_read_timeout == 120.0

    def test_custom_values(self):
        """Custom timeout values are applied."""
        config = QueryTimeoutConfig(
            read_timeout=10.0,
            write_timeout=20.0,
            complex_read_timeout=60.0,
        )
        assert config.read_timeout == 10.0
        assert config.write_timeout == 20.0
        assert config.complex_read_timeout == 60.0

    def test_config_is_frozen(self):
        """QueryTimeoutConfig is immutable."""
        config = QueryTimeoutConfig()
        with pytest.raises(Exception):  # Could be FrozenInstanceError or AttributeError
            config.read_timeout = 999  # type: ignore


# =============================================================================
# BaseRepository Initialization Tests
# =============================================================================


class TestBaseRepositoryInit:
    """Tests for BaseRepository initialization."""

    def test_init_with_default_timeout(self, mock_db_client):
        """Repository initializes with default timeout config."""
        repo = ConcreteRepository(mock_db_client)
        assert repo.client == mock_db_client
        assert repo.timeout_config == DEFAULT_QUERY_TIMEOUT

    def test_init_with_custom_timeout(self, mock_db_client):
        """Repository initializes with custom timeout config."""
        custom_config = QueryTimeoutConfig(read_timeout=5.0)
        repo = ConcreteRepository(mock_db_client, timeout_config=custom_config)
        assert repo.timeout_config.read_timeout == 5.0

    def test_init_validates_node_label(self, mock_db_client):
        """Repository validates node_label at initialization."""

        class InvalidLabelRepo(ConcreteRepository):
            @property
            def node_label(self) -> str:
                return "Invalid-Label"

        with pytest.raises(ValueError, match="Invalid node_label"):
            InvalidLabelRepo(mock_db_client)


# =============================================================================
# Helper Method Tests
# =============================================================================


class TestHelperMethods:
    """Tests for repository helper methods."""

    def test_generate_id_returns_uuid(self, repository):
        """_generate_id returns valid UUID string."""
        generated_id = repository._generate_id()
        # Should be valid UUID format
        assert UUID(generated_id)
        assert isinstance(generated_id, str)

    def test_generate_id_returns_unique_ids(self, repository):
        """_generate_id returns unique values."""
        ids = [repository._generate_id() for _ in range(100)]
        assert len(set(ids)) == 100

    def test_now_returns_utc_datetime(self, repository):
        """_now returns UTC timezone-aware datetime."""
        now = repository._now()
        assert isinstance(now, datetime)
        assert now.tzinfo == UTC

    def test_to_model_valid_record(self, repository, sample_entity_data):
        """_to_model converts valid record to model."""
        model = repository._to_model(sample_entity_data)
        assert model is not None
        assert model.id == "test-id-123"
        assert model.name == "Test Entity"
        assert model.value == 42

    def test_to_model_empty_record_returns_none(self, repository):
        """_to_model returns None for empty record."""
        assert repository._to_model({}) is None
        assert repository._to_model(None) is None  # type: ignore

    def test_to_model_invalid_record_returns_none(self, repository):
        """_to_model returns None for invalid record."""
        invalid_record = {"invalid": "data"}
        result = repository._to_model(invalid_record)
        assert result is None

    def test_to_models_converts_list(self, repository, sample_entity_data):
        """_to_models converts list of records."""
        records = [sample_entity_data, sample_entity_data]
        models = repository._to_models(records)
        assert len(models) == 2
        assert all(isinstance(m, TestModel) for m in models)

    def test_to_models_filters_invalid(self, repository, sample_entity_data):
        """_to_models filters out invalid records."""
        records = [sample_entity_data, {"invalid": "data"}, sample_entity_data]
        models = repository._to_models(records)
        assert len(models) == 2


# =============================================================================
# Get By ID Tests
# =============================================================================


class TestGetById:
    """Tests for get_by_id method."""

    @pytest.mark.asyncio
    async def test_get_by_id_found(self, repository, mock_db_client, sample_entity_data):
        """get_by_id returns entity when found."""
        mock_db_client.execute_single.return_value = {"entity": sample_entity_data}

        result = await repository.get_by_id("test-id-123")

        assert result is not None
        assert result.id == "test-id-123"
        mock_db_client.execute_single.assert_called_once()

        # Verify query structure
        call_args = mock_db_client.execute_single.call_args
        query = call_args[0][0]
        params = call_args[0][1]
        assert "MATCH (n:TestNode {id: $id})" in query
        assert params["id"] == "test-id-123"

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, repository, mock_db_client):
        """get_by_id returns None when not found."""
        mock_db_client.execute_single.return_value = None

        result = await repository.get_by_id("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_id_empty_entity(self, repository, mock_db_client):
        """get_by_id returns None when entity is empty."""
        mock_db_client.execute_single.return_value = {"entity": None}

        result = await repository.get_by_id("test-id")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_id_uses_read_timeout(self, repository, mock_db_client):
        """get_by_id uses read timeout configuration."""
        mock_db_client.execute_single.return_value = None

        await repository.get_by_id("test-id")

        call_args = mock_db_client.execute_single.call_args
        assert call_args.kwargs.get("timeout") == repository.timeout_config.read_timeout


# =============================================================================
# Get All Tests
# =============================================================================


class TestGetAll:
    """Tests for get_all method."""

    @pytest.mark.asyncio
    async def test_get_all_returns_entities(self, repository, mock_db_client, sample_entity_data):
        """get_all returns list of entities."""
        mock_db_client.execute.return_value = [
            {"entity": sample_entity_data},
            {"entity": {**sample_entity_data, "id": "test-id-456"}},
        ]

        result = await repository.get_all()

        assert len(result) == 2
        assert result[0].id == "test-id-123"
        assert result[1].id == "test-id-456"

    @pytest.mark.asyncio
    async def test_get_all_with_pagination(self, repository, mock_db_client):
        """get_all respects skip and limit parameters."""
        mock_db_client.execute.return_value = []

        await repository.get_all(skip=10, limit=20)

        call_args = mock_db_client.execute.call_args
        params = call_args[0][1]
        assert params["skip"] == 10
        assert params["limit"] == 20

    @pytest.mark.asyncio
    async def test_get_all_caps_limit(self, repository, mock_db_client):
        """get_all caps limit at 100."""
        mock_db_client.execute.return_value = []

        await repository.get_all(limit=1000)

        call_args = mock_db_client.execute.call_args
        params = call_args[0][1]
        assert params["limit"] == 100

    @pytest.mark.asyncio
    async def test_get_all_enforces_minimum_limit(self, repository, mock_db_client):
        """get_all enforces minimum limit of 1."""
        mock_db_client.execute.return_value = []

        await repository.get_all(limit=0)

        call_args = mock_db_client.execute.call_args
        params = call_args[0][1]
        assert params["limit"] == 1

    @pytest.mark.asyncio
    async def test_get_all_enforces_non_negative_skip(self, repository, mock_db_client):
        """get_all enforces non-negative skip."""
        mock_db_client.execute.return_value = []

        await repository.get_all(skip=-10)

        call_args = mock_db_client.execute.call_args
        params = call_args[0][1]
        assert params["skip"] == 0

    @pytest.mark.asyncio
    async def test_get_all_with_order_by(self, repository, mock_db_client):
        """get_all respects order_by parameter."""
        mock_db_client.execute.return_value = []

        await repository.get_all(order_by="name", order_dir="ASC")

        call_args = mock_db_client.execute.call_args
        query = call_args[0][0]
        assert "ORDER BY n.name ASC" in query

    @pytest.mark.asyncio
    async def test_get_all_validates_order_by(self, repository, mock_db_client):
        """get_all validates order_by field name."""
        with pytest.raises(ValueError, match="Invalid order_by"):
            await repository.get_all(order_by="invalid; DROP TABLE")

    @pytest.mark.asyncio
    async def test_get_all_defaults_invalid_order_dir(self, repository, mock_db_client):
        """get_all defaults invalid order_dir to DESC."""
        mock_db_client.execute.return_value = []

        await repository.get_all(order_dir="INVALID")

        call_args = mock_db_client.execute.call_args
        query = call_args[0][0]
        assert "DESC" in query

    @pytest.mark.asyncio
    async def test_get_all_empty_result(self, repository, mock_db_client):
        """get_all returns empty list when no entities."""
        mock_db_client.execute.return_value = []

        result = await repository.get_all()

        assert result == []


# =============================================================================
# Count Tests
# =============================================================================


class TestCount:
    """Tests for count method."""

    @pytest.mark.asyncio
    async def test_count_returns_total(self, repository, mock_db_client):
        """count returns total entity count."""
        mock_db_client.execute_single.return_value = {"count": 42}

        result = await repository.count()

        assert result == 42

    @pytest.mark.asyncio
    async def test_count_returns_zero_when_empty(self, repository, mock_db_client):
        """count returns 0 when no entities."""
        mock_db_client.execute_single.return_value = {"count": 0}

        result = await repository.count()

        assert result == 0

    @pytest.mark.asyncio
    async def test_count_returns_zero_on_none_result(self, repository, mock_db_client):
        """count returns 0 when result is None."""
        mock_db_client.execute_single.return_value = None

        result = await repository.count()

        assert result == 0

    @pytest.mark.asyncio
    async def test_count_query_structure(self, repository, mock_db_client):
        """count uses correct query structure."""
        mock_db_client.execute_single.return_value = {"count": 0}

        await repository.count()

        call_args = mock_db_client.execute_single.call_args
        query = call_args[0][0]
        assert "MATCH (n:TestNode)" in query
        assert "count(n)" in query


# =============================================================================
# Exists Tests
# =============================================================================


class TestExists:
    """Tests for exists method."""

    @pytest.mark.asyncio
    async def test_exists_returns_true_when_found(self, repository, mock_db_client):
        """exists returns True when entity exists."""
        mock_db_client.execute_single.return_value = {"exists": True}

        result = await repository.exists("test-id")

        assert result is True

    @pytest.mark.asyncio
    async def test_exists_returns_false_when_not_found(self, repository, mock_db_client):
        """exists returns False when entity not found."""
        mock_db_client.execute_single.return_value = {"exists": False}

        result = await repository.exists("nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_exists_returns_false_on_none_result(self, repository, mock_db_client):
        """exists returns False when result is None."""
        mock_db_client.execute_single.return_value = None

        result = await repository.exists("test-id")

        assert result is False

    @pytest.mark.asyncio
    async def test_exists_query_structure(self, repository, mock_db_client):
        """exists uses correct query structure."""
        mock_db_client.execute_single.return_value = {"exists": False}

        await repository.exists("test-id-123")

        call_args = mock_db_client.execute_single.call_args
        query = call_args[0][0]
        params = call_args[0][1]
        assert "MATCH (n:TestNode {id: $id})" in query
        assert "count(n) > 0" in query
        assert params["id"] == "test-id-123"


# =============================================================================
# Delete Tests
# =============================================================================


class TestDelete:
    """Tests for delete method."""

    @pytest.mark.asyncio
    async def test_delete_returns_true_when_deleted(self, repository, mock_db_client):
        """delete returns True when entity is deleted."""
        mock_db_client.execute_single.return_value = {"deleted": 1}

        result = await repository.delete("test-id")

        assert result is True

    @pytest.mark.asyncio
    async def test_delete_returns_false_when_not_found(self, repository, mock_db_client):
        """delete returns False when entity not found."""
        mock_db_client.execute_single.return_value = {"deleted": 0}

        result = await repository.delete("nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_delete_returns_false_on_none_result(self, repository, mock_db_client):
        """delete returns False when result is None."""
        mock_db_client.execute_single.return_value = None

        result = await repository.delete("test-id")

        assert result is False

    @pytest.mark.asyncio
    async def test_delete_uses_detach_delete(self, repository, mock_db_client):
        """delete uses DETACH DELETE to remove relationships."""
        mock_db_client.execute_single.return_value = {"deleted": 1}

        await repository.delete("test-id")

        call_args = mock_db_client.execute_single.call_args
        query = call_args[0][0]
        assert "DETACH DELETE" in query

    @pytest.mark.asyncio
    async def test_delete_uses_write_timeout(self, repository, mock_db_client):
        """delete uses write timeout configuration."""
        mock_db_client.execute_single.return_value = {"deleted": 1}

        await repository.delete("test-id")

        call_args = mock_db_client.execute_single.call_args
        assert call_args.kwargs.get("timeout") == repository.timeout_config.write_timeout


# =============================================================================
# Update Field Tests
# =============================================================================


class TestUpdateField:
    """Tests for update_field method."""

    @pytest.mark.asyncio
    async def test_update_field_success(self, repository, mock_db_client, sample_entity_data):
        """update_field updates single field successfully."""
        updated_data = {**sample_entity_data, "name": "Updated Name"}
        mock_db_client.execute_single.return_value = {"entity": updated_data}

        result = await repository.update_field("test-id", "name", "Updated Name")

        assert result is not None
        assert result.name == "Updated Name"

    @pytest.mark.asyncio
    async def test_update_field_validates_field_name(self, repository, mock_db_client):
        """update_field validates field name."""
        with pytest.raises(ValueError, match="Invalid field"):
            await repository.update_field("test-id", "invalid; DROP", "value")

    @pytest.mark.asyncio
    async def test_update_field_returns_none_when_not_found(self, repository, mock_db_client):
        """update_field returns None when entity not found."""
        mock_db_client.execute_single.return_value = None

        result = await repository.update_field("nonexistent", "name", "value")

        assert result is None

    @pytest.mark.asyncio
    async def test_update_field_sets_updated_at(
        self, repository, mock_db_client, sample_entity_data
    ):
        """update_field sets updated_at timestamp."""
        mock_db_client.execute_single.return_value = {"entity": sample_entity_data}

        await repository.update_field("test-id", "name", "value")

        call_args = mock_db_client.execute_single.call_args
        query = call_args[0][0]
        params = call_args[0][1]
        assert "n.updated_at = $now" in query
        assert "now" in params


# =============================================================================
# Find By Field Tests
# =============================================================================


class TestFindByField:
    """Tests for find_by_field method."""

    @pytest.mark.asyncio
    async def test_find_by_field_returns_matches(
        self, repository, mock_db_client, sample_entity_data
    ):
        """find_by_field returns matching entities."""
        mock_db_client.execute.return_value = [
            {"entity": sample_entity_data},
            {"entity": {**sample_entity_data, "id": "test-id-456"}},
        ]

        result = await repository.find_by_field("name", "Test Entity")

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_find_by_field_validates_field_name(self, repository, mock_db_client):
        """find_by_field validates field name."""
        with pytest.raises(ValueError, match="Invalid field"):
            await repository.find_by_field("invalid-field", "value")

    @pytest.mark.asyncio
    async def test_find_by_field_respects_limit(self, repository, mock_db_client):
        """find_by_field respects limit parameter."""
        mock_db_client.execute.return_value = []

        await repository.find_by_field("name", "value", limit=50)

        call_args = mock_db_client.execute.call_args
        params = call_args[0][1]
        assert params["limit"] == 50

    @pytest.mark.asyncio
    async def test_find_by_field_caps_limit(self, repository, mock_db_client):
        """find_by_field caps limit at 100."""
        mock_db_client.execute.return_value = []

        await repository.find_by_field("name", "value", limit=1000)

        call_args = mock_db_client.execute.call_args
        params = call_args[0][1]
        assert params["limit"] == 100

    @pytest.mark.asyncio
    async def test_find_by_field_returns_empty_list_when_no_matches(
        self, repository, mock_db_client
    ):
        """find_by_field returns empty list when no matches."""
        mock_db_client.execute.return_value = []

        result = await repository.find_by_field("name", "nonexistent")

        assert result == []

    @pytest.mark.asyncio
    async def test_find_by_field_query_structure(self, repository, mock_db_client):
        """find_by_field uses correct query structure."""
        mock_db_client.execute.return_value = []

        await repository.find_by_field("status", "active")

        call_args = mock_db_client.execute.call_args
        query = call_args[0][0]
        params = call_args[0][1]
        assert "MATCH (n:TestNode {status: $value})" in query
        assert params["value"] == "active"


# =============================================================================
# Create and Update Tests (Concrete Implementation)
# =============================================================================


class TestConcreteCreate:
    """Tests for concrete create implementation."""

    @pytest.mark.asyncio
    async def test_create_success(self, repository, mock_db_client, sample_entity_data):
        """create creates entity successfully."""
        mock_db_client.execute_single.return_value = {"entity": sample_entity_data}

        data = TestCreateModel(name="Test Entity", value=42)
        result = await repository.create(data)

        assert result.name == "Test Entity"
        assert result.value == 42
        mock_db_client.execute_single.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_generates_id(self, repository, mock_db_client, sample_entity_data):
        """create generates unique ID."""
        mock_db_client.execute_single.return_value = {"entity": sample_entity_data}

        data = TestCreateModel(name="Test")
        await repository.create(data)

        call_args = mock_db_client.execute_single.call_args
        params = call_args[0][1]
        assert "id" in params
        # Verify it's a valid UUID
        UUID(params["id"])

    @pytest.mark.asyncio
    async def test_create_raises_on_failure(self, repository, mock_db_client):
        """create raises RuntimeError on failure."""
        mock_db_client.execute_single.return_value = None

        data = TestCreateModel(name="Test")
        with pytest.raises(RuntimeError, match="Failed to create"):
            await repository.create(data)


class TestConcreteUpdate:
    """Tests for concrete update implementation."""

    @pytest.mark.asyncio
    async def test_update_success(self, repository, mock_db_client, sample_entity_data):
        """update updates entity successfully."""
        updated_data = {**sample_entity_data, "name": "Updated"}
        mock_db_client.execute_single.return_value = {"entity": updated_data}

        data = TestUpdateModel(name="Updated")
        result = await repository.update("test-id", data)

        assert result is not None
        assert result.name == "Updated"

    @pytest.mark.asyncio
    async def test_update_partial(self, repository, mock_db_client, sample_entity_data):
        """update with partial data only updates specified fields."""
        mock_db_client.execute_single.return_value = {"entity": sample_entity_data}

        data = TestUpdateModel(name="Updated")
        await repository.update("test-id", data)

        call_args = mock_db_client.execute_single.call_args
        params = call_args[0][1]
        assert "name" in params
        assert "value" not in params

    @pytest.mark.asyncio
    async def test_update_returns_none_when_not_found(self, repository, mock_db_client):
        """update returns None when entity not found."""
        mock_db_client.execute_single.return_value = None

        data = TestUpdateModel(name="Updated")
        result = await repository.update("nonexistent", data)

        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
