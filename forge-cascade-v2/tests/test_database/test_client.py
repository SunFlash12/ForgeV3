"""
Neo4j Client Tests for Forge Cascade V2

Comprehensive tests for the Neo4jClient including:
- Connection management (connect, close, reconnect)
- Query execution methods (execute, execute_single, execute_write, run)
- Transaction management with context managers
- Session management
- Health checks and connection verification
- Singleton pattern (get_db_client, close_db_client)
- Retry logic for transient errors
- Error handling for connection failures
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from neo4j.exceptions import ServiceUnavailable, SessionExpired, TransientError

from forge.database.client import (
    RETRYABLE_EXCEPTIONS,
    Neo4jClient,
    _get_lock,
    close_db_client,
    get_db_client,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_driver():
    """Create a mock Neo4j async driver."""
    driver = AsyncMock()
    driver.verify_connectivity = AsyncMock()
    driver.close = AsyncMock()
    return driver


@pytest.fixture
def mock_session():
    """Create a mock Neo4j async session."""
    session = AsyncMock()
    session.run = AsyncMock()
    session.begin_transaction = AsyncMock()
    return session


@pytest.fixture
def mock_transaction():
    """Create a mock Neo4j async transaction."""
    tx = AsyncMock()
    tx.run = AsyncMock()
    tx.commit = AsyncMock()
    tx.rollback = AsyncMock()
    tx.closed = MagicMock(return_value=False)
    return tx


@pytest.fixture
def mock_result():
    """Create a mock Neo4j result."""
    result = AsyncMock()
    result.single = AsyncMock()
    result.consume = AsyncMock()
    return result


@pytest.fixture
def mock_record():
    """Create a mock Neo4j record."""
    record = MagicMock()
    record.__iter__ = MagicMock(return_value=iter([("key", "value")]))
    return record


@pytest.fixture
def mock_summary():
    """Create a mock query result summary."""
    summary = MagicMock()
    summary.counters = MagicMock()
    summary.counters.nodes_created = 1
    summary.counters.nodes_deleted = 0
    summary.counters.relationships_created = 2
    summary.counters.relationships_deleted = 0
    summary.counters.properties_set = 5
    return summary


@pytest.fixture
def neo4j_client():
    """Create a Neo4jClient instance for testing."""
    with patch("forge.database.client.settings") as mock_settings:
        mock_settings.neo4j_uri = "bolt://localhost:7687"
        mock_settings.neo4j_user = "neo4j"
        mock_settings.neo4j_password = "testpassword"
        mock_settings.neo4j_database = "neo4j"
        mock_settings.neo4j_max_connection_lifetime = 3600
        mock_settings.neo4j_max_connection_pool_size = 50
        mock_settings.neo4j_connection_timeout = 30.0
        return Neo4jClient()


@pytest.fixture
def neo4j_client_custom_params():
    """Create a Neo4jClient instance with custom parameters."""
    return Neo4jClient(
        uri="bolt://custom:7687",
        user="custom_user",
        password="custom_password",
        database="custom_db",
    )


# Reset the singleton between tests
@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the singleton client before each test."""
    import forge.database.client as client_module

    client_module._db_client = None
    client_module._db_client_lock = None
    yield
    client_module._db_client = None
    client_module._db_client_lock = None


# =============================================================================
# Initialization Tests
# =============================================================================


class TestNeo4jClientInit:
    """Tests for Neo4jClient initialization."""

    def test_init_with_default_settings(self, neo4j_client):
        """Client initializes with settings defaults."""
        assert neo4j_client._uri == "bolt://localhost:7687"
        assert neo4j_client._user == "neo4j"
        assert neo4j_client._password == "testpassword"
        assert neo4j_client._database == "neo4j"
        assert neo4j_client._driver is None
        assert neo4j_client._connected is False

    def test_init_with_custom_parameters(self, neo4j_client_custom_params):
        """Client initializes with custom parameters."""
        assert neo4j_client_custom_params._uri == "bolt://custom:7687"
        assert neo4j_client_custom_params._user == "custom_user"
        assert neo4j_client_custom_params._password == "custom_password"
        assert neo4j_client_custom_params._database == "custom_db"

    def test_is_connected_property_false_initially(self, neo4j_client):
        """is_connected returns False initially."""
        assert neo4j_client.is_connected is False

    def test_retryable_exceptions_defined(self):
        """Retryable exceptions are properly defined."""
        assert ServiceUnavailable in RETRYABLE_EXCEPTIONS
        assert SessionExpired in RETRYABLE_EXCEPTIONS
        assert TransientError in RETRYABLE_EXCEPTIONS


# =============================================================================
# Connection Tests
# =============================================================================


class TestNeo4jClientConnection:
    """Tests for connection management."""

    @pytest.mark.asyncio
    async def test_connect_success(self, neo4j_client, mock_driver):
        """Successful connection to Neo4j."""
        with patch(
            "forge.database.client.AsyncGraphDatabase.driver",
            return_value=mock_driver,
        ):
            await neo4j_client.connect()

            assert neo4j_client._driver is not None
            assert neo4j_client._connected is True
            mock_driver.verify_connectivity.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_already_connected(self, neo4j_client, mock_driver):
        """Connect returns early if already connected."""
        with patch(
            "forge.database.client.AsyncGraphDatabase.driver",
            return_value=mock_driver,
        ):
            await neo4j_client.connect()
            # Connect again
            await neo4j_client.connect()

            # Driver should only be created once
            assert mock_driver.verify_connectivity.call_count == 1

    @pytest.mark.asyncio
    async def test_connect_failure_service_unavailable(self, neo4j_client, mock_driver):
        """Connect raises on ServiceUnavailable."""
        mock_driver.verify_connectivity.side_effect = ServiceUnavailable("Cannot connect")

        with patch(
            "forge.database.client.AsyncGraphDatabase.driver",
            return_value=mock_driver,
        ):
            with pytest.raises(ServiceUnavailable):
                await neo4j_client.connect()

    @pytest.mark.asyncio
    async def test_connect_failure_session_expired(self, neo4j_client, mock_driver):
        """Connect raises on SessionExpired."""
        mock_driver.verify_connectivity.side_effect = SessionExpired("Session expired")

        with patch(
            "forge.database.client.AsyncGraphDatabase.driver",
            return_value=mock_driver,
        ):
            with pytest.raises(SessionExpired):
                await neo4j_client.connect()

    @pytest.mark.asyncio
    async def test_connect_failure_os_error(self, neo4j_client, mock_driver):
        """Connect raises on OSError."""
        mock_driver.verify_connectivity.side_effect = OSError("Network error")

        with patch(
            "forge.database.client.AsyncGraphDatabase.driver",
            return_value=mock_driver,
        ):
            with pytest.raises(OSError):
                await neo4j_client.connect()

    @pytest.mark.asyncio
    async def test_connect_failure_runtime_error(self, neo4j_client, mock_driver):
        """Connect raises on RuntimeError."""
        mock_driver.verify_connectivity.side_effect = RuntimeError("Runtime issue")

        with patch(
            "forge.database.client.AsyncGraphDatabase.driver",
            return_value=mock_driver,
        ):
            with pytest.raises(RuntimeError):
                await neo4j_client.connect()

    @pytest.mark.asyncio
    async def test_close_connection(self, neo4j_client, mock_driver):
        """Close connection properly."""
        with patch(
            "forge.database.client.AsyncGraphDatabase.driver",
            return_value=mock_driver,
        ):
            await neo4j_client.connect()
            await neo4j_client.close()

            assert neo4j_client._driver is None
            assert neo4j_client._connected is False
            mock_driver.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_when_not_connected(self, neo4j_client):
        """Close does nothing when not connected."""
        await neo4j_client.close()
        assert neo4j_client._driver is None

    @pytest.mark.asyncio
    async def test_reconnect_success(self, neo4j_client, mock_driver):
        """Reconnect closes and re-establishes connection."""
        mock_driver2 = AsyncMock()
        mock_driver2.verify_connectivity = AsyncMock()
        mock_driver2.close = AsyncMock()

        call_count = [0]

        def driver_factory(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_driver
            return mock_driver2

        with patch(
            "forge.database.client.AsyncGraphDatabase.driver",
            side_effect=driver_factory,
        ):
            await neo4j_client.connect()
            await neo4j_client.reconnect()

            # First driver should be closed
            mock_driver.close.assert_called_once()
            # New driver should be verified
            mock_driver2.verify_connectivity.assert_called_once()

    @pytest.mark.asyncio
    async def test_reconnect_handles_close_failure(self, neo4j_client, mock_driver):
        """Reconnect continues even if close fails."""
        mock_driver.close.side_effect = ServiceUnavailable("Cannot close")
        mock_driver2 = AsyncMock()
        mock_driver2.verify_connectivity = AsyncMock()

        call_count = [0]

        def driver_factory(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_driver
            return mock_driver2

        with patch(
            "forge.database.client.AsyncGraphDatabase.driver",
            side_effect=driver_factory,
        ):
            await neo4j_client.connect()
            # Should not raise even though close fails
            await neo4j_client.reconnect()

            # New connection should be established
            mock_driver2.verify_connectivity.assert_called_once()

    def test_is_connected_property_true_when_connected(self, neo4j_client, mock_driver):
        """is_connected returns True when driver is set and connected."""
        neo4j_client._driver = mock_driver
        neo4j_client._connected = True
        assert neo4j_client.is_connected is True

    def test_is_connected_false_when_driver_none(self, neo4j_client):
        """is_connected returns False when driver is None."""
        neo4j_client._driver = None
        neo4j_client._connected = True
        assert neo4j_client.is_connected is False

    def test_is_connected_false_when_not_connected(self, neo4j_client, mock_driver):
        """is_connected returns False when not connected flag."""
        neo4j_client._driver = mock_driver
        neo4j_client._connected = False
        assert neo4j_client.is_connected is False


# =============================================================================
# Session and Transaction Tests
# =============================================================================


class TestNeo4jClientSessionTransaction:
    """Tests for session and transaction management."""

    @pytest.mark.asyncio
    async def test_session_context_manager(self, neo4j_client, mock_driver, mock_session):
        """Session context manager works correctly."""
        mock_driver.session = MagicMock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        neo4j_client._driver = mock_driver

        async with neo4j_client.session() as session:
            assert session is mock_session

    @pytest.mark.asyncio
    async def test_session_raises_when_not_connected(self, neo4j_client):
        """Session raises RuntimeError when not connected."""
        with pytest.raises(RuntimeError, match="Neo4j client not connected"):
            async with neo4j_client.session():
                pass

    @pytest.mark.asyncio
    async def test_transaction_context_manager_success(
        self, neo4j_client, mock_driver, mock_session, mock_transaction
    ):
        """Transaction commits on successful exit."""
        mock_driver.session = MagicMock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.begin_transaction = AsyncMock(return_value=mock_transaction)

        neo4j_client._driver = mock_driver

        async with neo4j_client.transaction() as tx:
            assert tx is mock_transaction

        mock_transaction.commit.assert_called_once()
        mock_transaction.rollback.assert_not_called()

    @pytest.mark.asyncio
    async def test_transaction_rollback_on_exception(
        self, neo4j_client, mock_driver, mock_session, mock_transaction
    ):
        """Transaction rolls back on exception."""
        mock_driver.session = MagicMock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.begin_transaction = AsyncMock(return_value=mock_transaction)

        neo4j_client._driver = mock_driver

        with pytest.raises(ValueError):
            async with neo4j_client.transaction() as tx:
                raise ValueError("Test error")

        mock_transaction.rollback.assert_called_once()
        mock_transaction.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_transaction_no_rollback_if_closed(
        self, neo4j_client, mock_driver, mock_session, mock_transaction
    ):
        """Transaction does not rollback if already closed."""
        mock_driver.session = MagicMock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.begin_transaction = AsyncMock(return_value=mock_transaction)
        mock_transaction.closed = MagicMock(return_value=True)

        neo4j_client._driver = mock_driver

        with pytest.raises(ValueError):
            async with neo4j_client.transaction() as tx:
                raise ValueError("Test error")

        mock_transaction.rollback.assert_not_called()

    @pytest.mark.asyncio
    async def test_transaction_raises_when_not_connected(self, neo4j_client):
        """Transaction raises RuntimeError when not connected."""
        with pytest.raises(RuntimeError, match="Neo4j client not connected"):
            async with neo4j_client.transaction():
                pass


# =============================================================================
# Query Execution Tests
# =============================================================================


class TestNeo4jClientExecute:
    """Tests for query execution methods."""

    @pytest.mark.asyncio
    async def test_execute_returns_list_of_dicts(
        self, neo4j_client, mock_driver, mock_session, mock_result
    ):
        """Execute returns list of dictionaries."""
        mock_driver.session = MagicMock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        # Create mock records
        record1 = MagicMock()
        record1.keys = MagicMock(return_value=["name", "value"])
        record1.values = MagicMock(return_value=["test", 123])
        record1.__iter__ = MagicMock(return_value=iter([("name", "test"), ("value", 123)]))

        async def mock_iter():
            yield record1

        mock_result.__aiter__ = mock_iter
        mock_session.run = AsyncMock(return_value=mock_result)

        neo4j_client._driver = mock_driver

        results = await neo4j_client.execute("MATCH (n) RETURN n", {"param": "value"})

        assert isinstance(results, list)
        mock_session.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_with_timeout(self, neo4j_client, mock_driver, mock_session, mock_result):
        """Execute passes timeout parameter."""
        mock_driver.session = MagicMock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        async def mock_iter():
            return
            yield  # Make this an async generator

        mock_result.__aiter__ = mock_iter
        mock_session.run = AsyncMock(return_value=mock_result)

        neo4j_client._driver = mock_driver

        await neo4j_client.execute("RETURN 1", timeout=5.0)

        mock_session.run.assert_called_once_with("RETURN 1", {}, timeout=5.0)

    @pytest.mark.asyncio
    async def test_execute_with_none_parameters(
        self, neo4j_client, mock_driver, mock_session, mock_result
    ):
        """Execute handles None parameters."""
        mock_driver.session = MagicMock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        async def mock_iter():
            return
            yield

        mock_result.__aiter__ = mock_iter
        mock_session.run = AsyncMock(return_value=mock_result)

        neo4j_client._driver = mock_driver

        await neo4j_client.execute("RETURN 1")

        mock_session.run.assert_called_once_with("RETURN 1", {}, timeout=None)

    @pytest.mark.asyncio
    async def test_execute_single_returns_dict(
        self, neo4j_client, mock_driver, mock_session, mock_result
    ):
        """Execute single returns a single dictionary."""
        mock_driver.session = MagicMock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        record = MagicMock()
        record.__iter__ = MagicMock(return_value=iter([("key", "value")]))
        mock_result.single = AsyncMock(return_value=record)
        mock_session.run = AsyncMock(return_value=mock_result)

        neo4j_client._driver = mock_driver

        result = await neo4j_client.execute_single("RETURN 1 as key")

        assert result is not None
        mock_result.single.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_single_returns_none_when_no_result(
        self, neo4j_client, mock_driver, mock_session, mock_result
    ):
        """Execute single returns None when no result."""
        mock_driver.session = MagicMock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        mock_result.single = AsyncMock(return_value=None)
        mock_session.run = AsyncMock(return_value=mock_result)

        neo4j_client._driver = mock_driver

        result = await neo4j_client.execute_single("MATCH (n:NotExists) RETURN n")

        assert result is None

    @pytest.mark.asyncio
    async def test_execute_write_returns_summary(
        self, neo4j_client, mock_driver, mock_session, mock_result, mock_summary
    ):
        """Execute write returns result summary."""
        mock_driver.session = MagicMock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        mock_result.consume = AsyncMock(return_value=mock_summary)
        mock_session.run = AsyncMock(return_value=mock_result)

        neo4j_client._driver = mock_driver

        result = await neo4j_client.execute_write("CREATE (n:Test {name: $name})", {"name": "test"})

        assert result["nodes_created"] == 1
        assert result["nodes_deleted"] == 0
        assert result["relationships_created"] == 2
        assert result["relationships_deleted"] == 0
        assert result["properties_set"] == 5

    @pytest.mark.asyncio
    async def test_run_is_alias_for_execute(
        self, neo4j_client, mock_driver, mock_session, mock_result
    ):
        """Run method is an alias for execute."""
        mock_driver.session = MagicMock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        async def mock_iter():
            return
            yield

        mock_result.__aiter__ = mock_iter
        mock_session.run = AsyncMock(return_value=mock_result)

        neo4j_client._driver = mock_driver

        result = await neo4j_client.run("RETURN 1", {"param": "value"}, timeout=10.0)

        assert isinstance(result, list)
        mock_session.run.assert_called_once_with("RETURN 1", {"param": "value"}, timeout=10.0)


# =============================================================================
# Health Check Tests
# =============================================================================


class TestNeo4jClientHealthCheck:
    """Tests for health check operations."""

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, neo4j_client, mock_driver, mock_session, mock_result):
        """Health check returns healthy status."""
        mock_driver.session = MagicMock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        record = MagicMock()
        record.__iter__ = MagicMock(
            return_value=iter([("name", "Neo4j"), ("versions", ["5.0"]), ("edition", "Enterprise")])
        )
        mock_result.single = AsyncMock(return_value=record)
        mock_session.run = AsyncMock(return_value=mock_result)

        neo4j_client._driver = mock_driver
        neo4j_client._database = "neo4j"

        result = await neo4j_client.health_check()

        assert result["status"] == "healthy"
        assert result["database"] == "neo4j"
        assert "details" in result

    @pytest.mark.asyncio
    async def test_health_check_unhealthy_service_unavailable(
        self, neo4j_client, mock_driver, mock_session
    ):
        """Health check returns unhealthy on ServiceUnavailable."""
        mock_driver.session = MagicMock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.run = AsyncMock(side_effect=ServiceUnavailable("Unavailable"))

        neo4j_client._driver = mock_driver
        neo4j_client._database = "neo4j"

        result = await neo4j_client.health_check()

        assert result["status"] == "unhealthy"
        assert "error" in result

    @pytest.mark.asyncio
    async def test_health_check_unhealthy_session_expired(
        self, neo4j_client, mock_driver, mock_session
    ):
        """Health check returns unhealthy on SessionExpired."""
        mock_driver.session = MagicMock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.run = AsyncMock(side_effect=SessionExpired("Expired"))

        neo4j_client._driver = mock_driver
        neo4j_client._database = "neo4j"

        result = await neo4j_client.health_check()

        assert result["status"] == "unhealthy"

    @pytest.mark.asyncio
    async def test_health_check_unhealthy_transient_error(
        self, neo4j_client, mock_driver, mock_session
    ):
        """Health check returns unhealthy on TransientError."""
        mock_driver.session = MagicMock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.run = AsyncMock(side_effect=TransientError("Transient"))

        neo4j_client._driver = mock_driver
        neo4j_client._database = "neo4j"

        result = await neo4j_client.health_check()

        assert result["status"] == "unhealthy"

    @pytest.mark.asyncio
    async def test_verify_connection_true_when_healthy(
        self, neo4j_client, mock_driver, mock_session, mock_result
    ):
        """Verify connection returns True when healthy."""
        mock_driver.session = MagicMock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        record = MagicMock()
        record.__iter__ = MagicMock(return_value=iter([("name", "Neo4j")]))
        mock_result.single = AsyncMock(return_value=record)
        mock_session.run = AsyncMock(return_value=mock_result)

        neo4j_client._driver = mock_driver
        neo4j_client._database = "neo4j"

        result = await neo4j_client.verify_connection()

        assert result is True

    @pytest.mark.asyncio
    async def test_verify_connection_false_when_unhealthy(
        self, neo4j_client, mock_driver, mock_session
    ):
        """Verify connection returns False when unhealthy."""
        mock_driver.session = MagicMock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.run = AsyncMock(side_effect=ServiceUnavailable("Unavailable"))

        neo4j_client._driver = mock_driver
        neo4j_client._database = "neo4j"

        result = await neo4j_client.verify_connection()

        assert result is False


# =============================================================================
# Singleton Tests
# =============================================================================


class TestNeo4jClientSingleton:
    """Tests for singleton pattern."""

    @pytest.mark.asyncio
    async def test_get_db_client_creates_singleton(self, mock_driver):
        """get_db_client creates a singleton client."""
        with patch(
            "forge.database.client.AsyncGraphDatabase.driver",
            return_value=mock_driver,
        ):
            with patch("forge.database.client.settings") as mock_settings:
                mock_settings.neo4j_uri = "bolt://localhost:7687"
                mock_settings.neo4j_user = "neo4j"
                mock_settings.neo4j_password = "testpassword"
                mock_settings.neo4j_database = "neo4j"
                mock_settings.neo4j_max_connection_lifetime = 3600
                mock_settings.neo4j_max_connection_pool_size = 50
                mock_settings.neo4j_connection_timeout = 30.0

                client1 = await get_db_client()
                client2 = await get_db_client()

                assert client1 is client2

    @pytest.mark.asyncio
    async def test_get_db_client_connects_on_first_call(self, mock_driver):
        """get_db_client connects on first call."""
        with patch(
            "forge.database.client.AsyncGraphDatabase.driver",
            return_value=mock_driver,
        ):
            with patch("forge.database.client.settings") as mock_settings:
                mock_settings.neo4j_uri = "bolt://localhost:7687"
                mock_settings.neo4j_user = "neo4j"
                mock_settings.neo4j_password = "testpassword"
                mock_settings.neo4j_database = "neo4j"
                mock_settings.neo4j_max_connection_lifetime = 3600
                mock_settings.neo4j_max_connection_pool_size = 50
                mock_settings.neo4j_connection_timeout = 30.0

                client = await get_db_client()

                assert client.is_connected is True
                mock_driver.verify_connectivity.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_db_client_closes_and_clears_singleton(self, mock_driver):
        """close_db_client closes and clears the singleton."""
        import forge.database.client as client_module

        with patch(
            "forge.database.client.AsyncGraphDatabase.driver",
            return_value=mock_driver,
        ):
            with patch("forge.database.client.settings") as mock_settings:
                mock_settings.neo4j_uri = "bolt://localhost:7687"
                mock_settings.neo4j_user = "neo4j"
                mock_settings.neo4j_password = "testpassword"
                mock_settings.neo4j_database = "neo4j"
                mock_settings.neo4j_max_connection_lifetime = 3600
                mock_settings.neo4j_max_connection_pool_size = 50
                mock_settings.neo4j_connection_timeout = 30.0

                await get_db_client()
                await close_db_client()

                assert client_module._db_client is None
                mock_driver.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_db_client_when_not_connected(self):
        """close_db_client does nothing when not connected."""
        import forge.database.client as client_module

        assert client_module._db_client is None
        await close_db_client()
        assert client_module._db_client is None

    def test_get_lock_creates_asyncio_lock(self):
        """_get_lock creates an asyncio.Lock."""
        import forge.database.client as client_module

        client_module._db_client_lock = None
        lock = _get_lock()

        assert isinstance(lock, asyncio.Lock)

    def test_get_lock_returns_same_lock(self):
        """_get_lock returns the same lock on subsequent calls."""
        import forge.database.client as client_module

        client_module._db_client_lock = None
        lock1 = _get_lock()
        lock2 = _get_lock()

        assert lock1 is lock2


# =============================================================================
# Retry Logic Tests
# =============================================================================


class TestNeo4jClientRetryLogic:
    """Tests for retry logic on transient errors."""

    @pytest.mark.asyncio
    async def test_execute_retries_on_service_unavailable(
        self, neo4j_client, mock_driver, mock_session, mock_result
    ):
        """Execute retries on ServiceUnavailable."""
        mock_driver.session = MagicMock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        # Fail twice, then succeed
        call_count = [0]

        async def mock_run(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] <= 2:
                raise ServiceUnavailable("Temporary failure")

            # Return result on third call
            async def mock_iter():
                return
                yield

            mock_result.__aiter__ = mock_iter
            return mock_result

        mock_session.run = mock_run

        neo4j_client._driver = mock_driver

        result = await neo4j_client.execute("RETURN 1")

        assert call_count[0] == 3
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_execute_raises_after_max_retries(self, neo4j_client, mock_driver, mock_session):
        """Execute raises after max retries exceeded."""
        mock_driver.session = MagicMock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.run = AsyncMock(side_effect=ServiceUnavailable("Persistent failure"))

        neo4j_client._driver = mock_driver

        with pytest.raises(ServiceUnavailable):
            await neo4j_client.execute("RETURN 1")

    @pytest.mark.asyncio
    async def test_execute_single_retries_on_transient_error(
        self, neo4j_client, mock_driver, mock_session, mock_result
    ):
        """Execute single retries on TransientError."""
        mock_driver.session = MagicMock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        call_count = [0]

        async def mock_run(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] <= 1:
                raise TransientError("Transient failure")

            record = MagicMock()
            record.__iter__ = MagicMock(return_value=iter([("key", "value")]))
            mock_result.single = AsyncMock(return_value=record)
            return mock_result

        mock_session.run = mock_run

        neo4j_client._driver = mock_driver

        result = await neo4j_client.execute_single("RETURN 1")

        assert call_count[0] == 2
        assert result is not None

    @pytest.mark.asyncio
    async def test_execute_write_retries_on_session_expired(
        self, neo4j_client, mock_driver, mock_session, mock_result, mock_summary
    ):
        """Execute write retries on SessionExpired."""
        mock_driver.session = MagicMock(return_value=mock_session)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        call_count = [0]

        async def mock_run(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] <= 1:
                raise SessionExpired("Session expired")

            mock_result.consume = AsyncMock(return_value=mock_summary)
            return mock_result

        mock_session.run = mock_run

        neo4j_client._driver = mock_driver

        result = await neo4j_client.execute_write("CREATE (n:Test)")

        assert call_count[0] == 2
        assert result["nodes_created"] == 1


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestNeo4jClientErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_get_driver_raises_when_not_connected(self, neo4j_client):
        """_get_driver raises RuntimeError when not connected."""
        with pytest.raises(RuntimeError, match="Neo4j client not connected"):
            neo4j_client._get_driver()

    @pytest.mark.asyncio
    async def test_execute_raises_on_connection_error(self, neo4j_client):
        """Execute raises when not connected."""
        with pytest.raises(RuntimeError, match="Neo4j client not connected"):
            await neo4j_client.execute("RETURN 1")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
