"""
Neo4j Async Client

Async wrapper for Neo4j Python driver with connection pooling,
transaction management, and retry logic.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import structlog
from neo4j import AsyncDriver, AsyncGraphDatabase, AsyncSession, AsyncTransaction
from neo4j.exceptions import (
    ServiceUnavailable,
    SessionExpired,
    TransientError,
)
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from forge.config import settings

logger = structlog.get_logger(__name__)


# Retry configuration for transient errors
RETRYABLE_EXCEPTIONS = (ServiceUnavailable, SessionExpired, TransientError)


class Neo4jClient:
    """
    Async Neo4j client for Forge.

    Provides connection pooling, transaction management,
    and helper methods for common operations.
    """

    def __init__(
        self,
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
        database: str | None = None,
    ):
        """
        Initialize Neo4j client.

        Args:
            uri: Neo4j connection URI (defaults to settings)
            user: Username (defaults to settings)
            password: Password (defaults to settings)
            database: Database name (defaults to settings)
        """
        self._uri = uri or settings.neo4j_uri
        self._user = user or settings.neo4j_user
        self._password = password or settings.neo4j_password
        self._database = database or settings.neo4j_database

        self._driver: AsyncDriver | None = None
        self._connected = False

    async def connect(self) -> None:
        """Establish connection to Neo4j."""
        if self._driver is not None:
            return

        logger.info(
            "Connecting to Neo4j",
            uri=self._uri,
            database=self._database,
        )

        self._driver = AsyncGraphDatabase.driver(
            self._uri,
            auth=(self._user, self._password),
            max_connection_lifetime=settings.neo4j_max_connection_lifetime,
            max_connection_pool_size=settings.neo4j_max_connection_pool_size,
            connection_timeout=settings.neo4j_connection_timeout,
        )

        # Verify connection
        try:
            await self._driver.verify_connectivity()
            self._connected = True
            logger.info("Neo4j connection established")
        except Exception as e:
            logger.error("Failed to connect to Neo4j", error=str(e))
            raise

    async def close(self) -> None:
        """Close the Neo4j connection."""
        if self._driver is not None:
            await self._driver.close()
            self._driver = None
            self._connected = False
            logger.info("Neo4j connection closed")

    @property
    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self._connected and self._driver is not None

    def _get_driver(self) -> AsyncDriver:
        """Get the driver instance, raising if not connected."""
        if self._driver is None:
            raise RuntimeError("Neo4j client not connected. Call connect() first.")
        return self._driver

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Get a Neo4j session.

        Usage:
            async with client.session() as session:
                result = await session.run("MATCH (n) RETURN n")
        """
        driver = self._get_driver()
        async with driver.session(database=self._database) as session:
            yield session

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[AsyncTransaction, None]:
        """
        Get a Neo4j transaction.

        Usage:
            async with client.transaction() as tx:
                await tx.run("CREATE (n:Node {name: $name})", name="test")

        Note: Transaction commits automatically on successful context exit.
        Rollback happens automatically on exception.
        """
        async with self.session() as session:
            tx = await session.begin_transaction()
            try:
                yield tx
                # Commit on successful exit
                await tx.commit()
            except Exception:
                # Rollback on error - check if transaction is still open
                # FIX: Use 'not tx.closed()' instead of 'tx.closed() is False'
                # to handle any falsy value correctly
                if not tx.closed():
                    await tx.rollback()
                raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
    )
    async def execute(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Execute a Cypher query and return results.

        Args:
            query: Cypher query string
            parameters: Query parameters

        Returns:
            List of result records as dictionaries
        """
        async with self.session() as session:
            result = await session.run(query, parameters or {})
            records = [dict(record) async for record in result]
            return records

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
    )
    async def execute_single(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """
        Execute a query and return a single result.

        Args:
            query: Cypher query string
            parameters: Query parameters

        Returns:
            Single result record or None
        """
        async with self.session() as session:
            result = await session.run(query, parameters or {})
            record = await result.single()
            return dict(record) if record else None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
    )
    async def execute_write(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Execute a write query within a transaction.

        Args:
            query: Cypher query string
            parameters: Query parameters

        Returns:
            Query result summary
        """
        async with self.session() as session:
            result = await session.run(query, parameters or {})
            summary = await result.consume()
            return {
                "nodes_created": summary.counters.nodes_created,
                "nodes_deleted": summary.counters.nodes_deleted,
                "relationships_created": summary.counters.relationships_created,
                "relationships_deleted": summary.counters.relationships_deleted,
                "properties_set": summary.counters.properties_set,
            }

    async def run(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Alias for execute() - provided for compatibility with agent code.

        Args:
            query: Cypher query string
            parameters: Query parameters

        Returns:
            List of result records as dictionaries
        """
        return await self.execute(query, parameters)

    async def health_check(self) -> dict[str, Any]:
        """
        Perform a health check on the database connection.

        Returns:
            Health check result
        """
        try:
            result = await self.execute_single(
                "CALL dbms.components() YIELD name, versions, edition "
                "RETURN name, versions, edition LIMIT 1"
            )
            return {
                "status": "healthy",
                "database": self._database,
                "details": result or {},
            }
        except Exception as e:
            logger.error("Neo4j health check failed", error=str(e))
            return {
                "status": "unhealthy",
                "database": self._database,
                "error": str(e),
            }

    async def verify_connection(self) -> bool:
        """
        Verify the database connection is working.

        Returns:
            True if connection is healthy, False otherwise
        """
        try:
            health = await self.health_check()
            return health.get("status") == "healthy"
        except Exception:
            return False


# ═══════════════════════════════════════════════════════════════
# CLIENT SINGLETON
# ═══════════════════════════════════════════════════════════════

import asyncio
import threading

_db_client: Neo4jClient | None = None
# SECURITY FIX (Audit 3): Initialize lock at module level to prevent race condition
# The lock must be created lazily because asyncio.Lock() requires an event loop.
# We use a threading.Lock to protect the lazy initialization of the async lock.
_db_client_lock: asyncio.Lock | None = None
_lock_init_lock = threading.Lock()  # Protects _db_client_lock initialization


def _get_lock() -> asyncio.Lock:
    """
    Get or create the singleton lock.

    SECURITY FIX (Audit 3): Uses double-checked locking pattern with threading.Lock
    to prevent race condition where multiple coroutines could create separate locks.
    """
    global _db_client_lock
    if _db_client_lock is None:
        with _lock_init_lock:
            if _db_client_lock is None:
                _db_client_lock = asyncio.Lock()
    return _db_client_lock


async def get_db_client() -> Neo4jClient:
    """
    Get the global database client instance.

    Creates and connects the client on first call.
    Thread-safe using asyncio.Lock to prevent race conditions.
    """
    global _db_client

    # Fast path - already initialized
    if _db_client is not None:
        return _db_client

    # Slow path - needs initialization with lock
    async with _get_lock():
        # Double-check after acquiring lock
        if _db_client is None:
            client = Neo4jClient()
            await client.connect()
            _db_client = client

    return _db_client


async def close_db_client() -> None:
    """Close the global database client."""
    global _db_client

    async with _get_lock():
        if _db_client is not None:
            await _db_client.close()
            _db_client = None
