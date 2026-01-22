"""
Revenue Repository

Persistent storage for RevenueRecord models in Neo4j.
This ensures revenue data survives server restarts and provides
query capabilities for analytics and pending distribution processing.
"""

import json
import logging
from datetime import datetime, UTC
from typing import Any

from ..models import RevenueRecord, RevenueType

logger = logging.getLogger(__name__)


class RevenueRepository:
    """
    Repository for revenue record persistence.

    Stores revenue records in Neo4j with the following structure:
    - (RevenueRecord) nodes containing all record fields
    - Indexed by id, source_entity_id, and timestamp for efficient querying
    """

    def __init__(self, neo4j_client):
        """
        Initialize repository with database client.

        Args:
            neo4j_client: Neo4j client instance for database operations
        """
        self.client = neo4j_client
        self.logger = logger

    async def create(self, record: RevenueRecord) -> RevenueRecord:
        """
        Create a new revenue record in the database.

        Args:
            record: The revenue record to persist

        Returns:
            The persisted record
        """
        query = """
        CREATE (r:RevenueRecord {
            id: $id,
            timestamp: $timestamp,
            revenue_type: $revenue_type,
            amount_virtual: $amount_virtual,
            amount_usd: $amount_usd,
            source_entity_id: $source_entity_id,
            source_entity_type: $source_entity_type,
            beneficiary_addresses: $beneficiary_addresses,
            distribution_complete: $distribution_complete,
            tx_hash: $tx_hash,
            metadata: $metadata
        })
        RETURN r.id as id
        """

        params = {
            "id": record.id,
            "timestamp": record.timestamp.isoformat() if record.timestamp else datetime.now(UTC).isoformat(),
            "revenue_type": record.revenue_type.value,
            "amount_virtual": record.amount_virtual,
            "amount_usd": record.amount_usd,
            "source_entity_id": record.source_entity_id,
            "source_entity_type": record.source_entity_type,
            "beneficiary_addresses": record.beneficiary_addresses,
            "distribution_complete": record.distribution_complete,
            "tx_hash": record.tx_hash,
            "metadata": json.dumps(record.metadata) if hasattr(record, 'metadata') else "{}",
        }

        try:
            await self.client.execute_write(query, parameters=params)
            self.logger.debug(f"Created revenue record {record.id}")
            return record
        except Exception as e:
            self.logger.error(f"Failed to create revenue record: {e}")
            raise

    async def update(self, record: RevenueRecord) -> RevenueRecord:
        """
        Update an existing revenue record.

        Args:
            record: The record with updated values

        Returns:
            The updated record
        """
        query = """
        MATCH (r:RevenueRecord {id: $id})
        SET r.distribution_complete = $distribution_complete,
            r.tx_hash = $tx_hash,
            r.updated_at = datetime()
        RETURN r.id as id
        """

        params = {
            "id": record.id,
            "distribution_complete": record.distribution_complete,
            "tx_hash": record.tx_hash,
        }

        try:
            await self.client.execute_write(query, parameters=params)
            self.logger.debug(f"Updated revenue record {record.id}")
            return record
        except Exception as e:
            self.logger.error(f"Failed to update revenue record: {e}")
            raise

    async def get_by_id(self, record_id: str) -> RevenueRecord | None:
        """
        Get a revenue record by ID.

        Args:
            record_id: The record ID

        Returns:
            The record or None if not found
        """
        query = """
        MATCH (r:RevenueRecord {id: $id})
        RETURN r {.*} as record
        """

        try:
            results = await self.client.execute_read(query, parameters={"id": record_id})
            if not results:
                return None
            return self._deserialize_record(results[0]["record"])
        except Exception as e:
            self.logger.error(f"Failed to get revenue record: {e}")
            return None

    async def query_pending(self) -> list[RevenueRecord]:
        """
        Query for records that haven't been distributed yet.

        Returns:
            List of pending revenue records
        """
        return await self.query(distribution_complete=False)

    async def query(
        self,
        entity_id: str | None = None,
        entity_type: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        distribution_complete: bool | None = None,
        revenue_type: RevenueType | None = None,
        limit: int = 1000,
    ) -> list[RevenueRecord]:
        """
        Query revenue records with filters.

        Args:
            entity_id: Filter by source entity ID
            entity_type: Filter by source entity type
            start_date: Filter by timestamp >= start_date
            end_date: Filter by timestamp <= end_date
            distribution_complete: Filter by distribution status
            revenue_type: Filter by revenue type
            limit: Maximum records to return

        Returns:
            List of matching revenue records
        """
        conditions = []
        params: dict[str, Any] = {"limit": limit}

        if entity_id:
            conditions.append("r.source_entity_id = $entity_id")
            params["entity_id"] = entity_id

        if entity_type:
            conditions.append("r.source_entity_type = $entity_type")
            params["entity_type"] = entity_type

        if start_date:
            conditions.append("datetime(r.timestamp) >= datetime($start_date)")
            params["start_date"] = start_date.isoformat()

        if end_date:
            conditions.append("datetime(r.timestamp) <= datetime($end_date)")
            params["end_date"] = end_date.isoformat()

        if distribution_complete is not None:
            conditions.append("r.distribution_complete = $distribution_complete")
            params["distribution_complete"] = distribution_complete

        if revenue_type:
            conditions.append("r.revenue_type = $revenue_type")
            params["revenue_type"] = revenue_type.value

        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

        query = f"""
        MATCH (r:RevenueRecord)
        {where_clause}
        RETURN r {{.*}} as record
        ORDER BY r.timestamp DESC
        LIMIT $limit
        """

        try:
            results = await self.client.execute_read(query, parameters=params)
            records = []
            for row in results:
                record = self._deserialize_record(row["record"])
                if record:
                    records.append(record)
            return records
        except Exception as e:
            self.logger.error(f"Failed to query revenue records: {e}")
            return []

    async def get_total_by_entity(
        self,
        entity_id: str,
        entity_type: str,
    ) -> float:
        """
        Get total revenue for a specific entity.

        Args:
            entity_id: Entity ID
            entity_type: Entity type

        Returns:
            Total revenue in VIRTUAL
        """
        query = """
        MATCH (r:RevenueRecord)
        WHERE r.source_entity_id = $entity_id
          AND r.source_entity_type = $entity_type
        RETURN sum(r.amount_virtual) as total
        """

        try:
            results = await self.client.execute_read(
                query,
                parameters={"entity_id": entity_id, "entity_type": entity_type}
            )
            if results and results[0]["total"]:
                return float(results[0]["total"])
            return 0.0
        except Exception as e:
            self.logger.error(f"Failed to get entity revenue total: {e}")
            return 0.0

    async def delete(self, record_id: str) -> bool:
        """
        Delete a revenue record.

        Args:
            record_id: The record ID to delete

        Returns:
            True if deleted, False otherwise
        """
        query = """
        MATCH (r:RevenueRecord {id: $id})
        DELETE r
        RETURN count(*) as deleted
        """

        try:
            await self.client.execute_write(
                query,
                parameters={"id": record_id}
            )
            return True
        except Exception as e:
            self.logger.error(f"Failed to delete revenue record: {e}")
            return False

    def _deserialize_record(self, data: dict[str, Any]) -> RevenueRecord | None:
        """
        Deserialize a record from Neo4j data.

        Args:
            data: Dictionary of record fields

        Returns:
            RevenueRecord or None if deserialization fails
        """
        if not data:
            return None

        try:
            timestamp = data.get("timestamp")
            if isinstance(timestamp, str):
                # Handle ISO format with or without timezone
                if timestamp.endswith("Z"):
                    timestamp = timestamp.replace("Z", "+00:00")
                try:
                    timestamp = datetime.fromisoformat(timestamp)
                except ValueError:
                    timestamp = datetime.now(UTC)
            elif timestamp is None:
                timestamp = datetime.now(UTC)

            # Parse metadata
            metadata = data.get("metadata", "{}")
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except json.JSONDecodeError:
                    metadata = {}

            return RevenueRecord(
                id=data["id"],
                timestamp=timestamp,
                revenue_type=RevenueType(data["revenue_type"]),
                amount_virtual=float(data.get("amount_virtual", 0)),
                amount_usd=data.get("amount_usd"),
                source_entity_id=data["source_entity_id"],
                source_entity_type=data["source_entity_type"],
                beneficiary_addresses=data.get("beneficiary_addresses", []),
                distribution_complete=data.get("distribution_complete", False),
                tx_hash=data.get("tx_hash"),
            )
        except Exception as e:
            self.logger.error(f"Failed to deserialize revenue record: {e}")
            return None


# Global repository instance
_revenue_repo: RevenueRepository | None = None


def get_revenue_repository(neo4j_client=None) -> RevenueRepository:
    """
    Get or create the revenue repository singleton.

    Args:
        neo4j_client: Optional Neo4j client (required for first call)

    Returns:
        RevenueRepository instance
    """
    global _revenue_repo

    if _revenue_repo is None:
        if neo4j_client is None:
            raise ValueError("Neo4j client required for first initialization")
        _revenue_repo = RevenueRepository(neo4j_client)

    return _revenue_repo
