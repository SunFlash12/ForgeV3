"""
Cascade Repository

Persistent storage for CascadeChain and CascadeEvent models.
Enables cascade state to survive server restarts.
"""

import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import structlog

from forge.database.client import Neo4jClient
from forge.models.events import CascadeChain, CascadeEvent

logger = structlog.get_logger(__name__)


class CascadeRepository:
    """
    Repository for cascade chain persistence.

    Stores cascade chains and their events in Neo4j with the following structure:
    - (CascadeChain) nodes containing chain metadata
    - (CascadeEvent) nodes for individual events
    - [:HAS_EVENT {order: N}] relationships linking chains to events
    """

    def __init__(self, client: Neo4jClient):
        """Initialize repository with database client."""
        self.client = client
        self.logger = logger.bind(repository="cascade")

    def _generate_id(self) -> str:
        """Generate a new unique ID."""
        return str(uuid4())

    def _now(self) -> datetime:
        """Get current UTC timestamp."""
        return datetime.now(UTC)

    def _serialize_event(self, event: CascadeEvent) -> dict[str, Any]:
        """Serialize a CascadeEvent for Neo4j storage."""
        return {
            "id": event.id,
            "source_overlay": event.source_overlay,
            "insight_type": event.insight_type,
            "insight_data": json.dumps(event.insight_data),
            "hop_count": event.hop_count,
            "max_hops": event.max_hops,
            "visited_overlays": event.visited_overlays,
            "impact_score": event.impact_score,
            "timestamp": event.timestamp.isoformat() if event.timestamp else None,
            "correlation_id": event.correlation_id,
        }

    def _deserialize_event(self, data: dict[str, Any]) -> CascadeEvent | None:
        """Deserialize a CascadeEvent from Neo4j storage."""
        if not data:
            return None
        try:
            insight_data = data.get("insight_data", "{}")
            if isinstance(insight_data, str):
                insight_data = json.loads(insight_data)

            timestamp = data.get("timestamp")
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp)

            return CascadeEvent(
                id=data["id"],
                source_overlay=data["source_overlay"],
                insight_type=data["insight_type"],
                insight_data=insight_data,
                hop_count=data.get("hop_count", 0),
                max_hops=data.get("max_hops", 5),
                visited_overlays=data.get("visited_overlays", []),
                impact_score=data.get("impact_score", 0.0),
                timestamp=timestamp,
                correlation_id=data.get("correlation_id"),
            )
        except Exception as e:
            self.logger.error("Failed to deserialize event", error=str(e))
            return None

    def _deserialize_chain(
        self, data: dict[str, Any], events: list[dict[str, Any]] | None = None
    ) -> CascadeChain | None:
        """Deserialize a CascadeChain from Neo4j storage."""
        if not data:
            return None
        try:
            initiated_at = data.get("initiated_at")
            if isinstance(initiated_at, str):
                initiated_at = datetime.fromisoformat(initiated_at)

            completed_at = data.get("completed_at")
            if isinstance(completed_at, str):
                completed_at = datetime.fromisoformat(completed_at)

            # Deserialize events
            event_list = []
            if events:
                for event_data in events:
                    event = self._deserialize_event(event_data)
                    if event:
                        event_list.append(event)

            return CascadeChain(
                cascade_id=data["cascade_id"],
                initiated_by=data["initiated_by"],
                initiated_at=initiated_at,
                events=event_list,
                completed_at=completed_at,
                total_hops=data.get("total_hops", 0),
                overlays_affected=data.get("overlays_affected", []),
                insights_generated=data.get("insights_generated", 0),
                actions_triggered=data.get("actions_triggered", 0),
                errors_encountered=data.get("errors_encountered", 0),
            )
        except Exception as e:
            self.logger.error("Failed to deserialize chain", error=str(e))
            return None

    async def create_chain(self, chain: CascadeChain) -> CascadeChain:
        """
        Create a new cascade chain in the database.

        Args:
            chain: The cascade chain to create

        Returns:
            The created chain
        """
        query = """
        CREATE (c:CascadeChain {
            cascade_id: $cascade_id,
            initiated_by: $initiated_by,
            initiated_at: $initiated_at,
            total_hops: $total_hops,
            overlays_affected: $overlays_affected,
            insights_generated: $insights_generated,
            actions_triggered: $actions_triggered,
            errors_encountered: $errors_encountered,
            status: 'active'
        })
        RETURN c {.*} AS chain
        """

        params = {
            "cascade_id": chain.cascade_id,
            "initiated_by": chain.initiated_by,
            "initiated_at": chain.initiated_at.isoformat() if chain.initiated_at else self._now().isoformat(),
            "total_hops": chain.total_hops,
            "overlays_affected": chain.overlays_affected,
            "insights_generated": chain.insights_generated,
            "actions_triggered": chain.actions_triggered,
            "errors_encountered": chain.errors_encountered,
        }

        await self.client.execute_single(query, params)

        # Create events if any
        for i, event in enumerate(chain.events):
            await self.add_event(chain.cascade_id, event, i)

        self.logger.info(
            "cascade_chain_created",
            cascade_id=chain.cascade_id,
            initiated_by=chain.initiated_by,
        )

        return chain

    async def add_event(
        self, cascade_id: str, event: CascadeEvent, order: int | None = None
    ) -> CascadeEvent:
        """
        Add an event to an existing cascade chain.

        Args:
            cascade_id: The cascade chain ID
            event: The event to add
            order: Optional explicit order (auto-calculated if not provided)

        Returns:
            The added event
        """
        # Calculate order if not provided
        if order is None:
            count_query = """
            MATCH (c:CascadeChain {cascade_id: $cascade_id})-[:HAS_EVENT]->(e:CascadeEvent)
            RETURN count(e) AS count
            """
            result = await self.client.execute_single(count_query, {"cascade_id": cascade_id})
            order = result["count"] if result else 0

        event_data = self._serialize_event(event)

        query = """
        MATCH (c:CascadeChain {cascade_id: $cascade_id})
        CREATE (e:CascadeEvent $event_data)
        CREATE (c)-[:HAS_EVENT {order: $order}]->(e)
        SET c.total_hops = c.total_hops + 1,
            c.insights_generated = c.insights_generated + 1
        RETURN e {.*} AS event
        """

        await self.client.execute_single(
            query,
            {
                "cascade_id": cascade_id,
                "event_data": event_data,
                "order": order,
            },
        )

        self.logger.debug(
            "cascade_event_added",
            cascade_id=cascade_id,
            event_id=event.id,
            hop_count=event.hop_count,
        )

        return event

    async def update_chain(self, chain: CascadeChain) -> CascadeChain:
        """
        Update an existing cascade chain.

        Args:
            chain: The chain with updated values

        Returns:
            The updated chain
        """
        query = """
        MATCH (c:CascadeChain {cascade_id: $cascade_id})
        SET c.total_hops = $total_hops,
            c.overlays_affected = $overlays_affected,
            c.insights_generated = $insights_generated,
            c.actions_triggered = $actions_triggered,
            c.errors_encountered = $errors_encountered
        RETURN c {.*} AS chain
        """

        await self.client.execute_single(
            query,
            {
                "cascade_id": chain.cascade_id,
                "total_hops": chain.total_hops,
                "overlays_affected": chain.overlays_affected,
                "insights_generated": chain.insights_generated,
                "actions_triggered": chain.actions_triggered,
                "errors_encountered": chain.errors_encountered,
            },
        )

        return chain

    async def complete_chain(self, cascade_id: str) -> CascadeChain | None:
        """
        Mark a cascade chain as complete.

        Args:
            cascade_id: The cascade chain ID

        Returns:
            The completed chain or None if not found
        """
        query = """
        MATCH (c:CascadeChain {cascade_id: $cascade_id})
        SET c.completed_at = $completed_at,
            c.status = 'completed'
        RETURN c {.*} AS chain
        """

        result = await self.client.execute_single(
            query,
            {
                "cascade_id": cascade_id,
                "completed_at": self._now().isoformat(),
            },
        )

        if not result:
            return None

        # Fetch events
        chain = await self.get_by_id(cascade_id)

        self.logger.info(
            "cascade_chain_completed",
            cascade_id=cascade_id,
        )

        return chain

    async def get_by_id(self, cascade_id: str) -> CascadeChain | None:
        """
        Get a cascade chain by ID with all its events.

        Args:
            cascade_id: The cascade chain ID

        Returns:
            The chain with events or None if not found
        """
        # Get chain and events in a single query
        query = """
        MATCH (c:CascadeChain {cascade_id: $cascade_id})
        OPTIONAL MATCH (c)-[r:HAS_EVENT]->(e:CascadeEvent)
        WITH c, e, r
        ORDER BY r.order ASC
        WITH c, collect(e {.*}) AS events
        RETURN c {.*} AS chain, events
        """

        result = await self.client.execute_single(query, {"cascade_id": cascade_id})

        if not result or not result.get("chain"):
            return None

        return self._deserialize_chain(result["chain"], result.get("events", []))

    async def get_active_chains(self) -> list[CascadeChain]:
        """
        Get all active (incomplete) cascade chains.

        Returns:
            List of active chains with their events
        """
        query = """
        MATCH (c:CascadeChain)
        WHERE c.status = 'active' OR c.completed_at IS NULL
        OPTIONAL MATCH (c)-[r:HAS_EVENT]->(e:CascadeEvent)
        WITH c, e, r
        ORDER BY r.order ASC
        WITH c, collect(e {.*}) AS events
        RETURN c {.*} AS chain, events
        ORDER BY c.initiated_at DESC
        """

        results = await self.client.execute(query, {})

        chains = []
        for result in results:
            chain = self._deserialize_chain(result.get("chain"), result.get("events", []))
            if chain:
                chains.append(chain)

        return chains

    async def get_completed_chains(
        self, limit: int = 100, skip: int = 0
    ) -> list[CascadeChain]:
        """
        Get completed cascade chains.

        Args:
            limit: Maximum chains to return
            skip: Number of chains to skip

        Returns:
            List of completed chains with their events
        """
        query = """
        MATCH (c:CascadeChain)
        WHERE c.status = 'completed' OR c.completed_at IS NOT NULL
        OPTIONAL MATCH (c)-[r:HAS_EVENT]->(e:CascadeEvent)
        WITH c, e, r
        ORDER BY r.order ASC
        WITH c, collect(e {.*}) AS events
        RETURN c {.*} AS chain, events
        ORDER BY c.completed_at DESC
        SKIP $skip
        LIMIT $limit
        """

        results = await self.client.execute(query, {"limit": limit, "skip": skip})

        chains = []
        for result in results:
            chain = self._deserialize_chain(result.get("chain"), result.get("events", []))
            if chain:
                chains.append(chain)

        return chains

    async def delete_chain(self, cascade_id: str) -> bool:
        """
        Delete a cascade chain and all its events.

        Args:
            cascade_id: The cascade chain ID

        Returns:
            True if deleted, False if not found
        """
        query = """
        MATCH (c:CascadeChain {cascade_id: $cascade_id})
        OPTIONAL MATCH (c)-[:HAS_EVENT]->(e:CascadeEvent)
        DETACH DELETE c, e
        RETURN count(c) AS deleted
        """

        result = await self.client.execute_single(query, {"cascade_id": cascade_id})

        deleted = result.get("deleted", 0) > 0 if result else False

        if deleted:
            self.logger.info("cascade_chain_deleted", cascade_id=cascade_id)

        return deleted

    async def cleanup_old_chains(self, days_old: int = 30) -> int:
        """
        Delete completed chains older than specified days.

        Args:
            days_old: Number of days after which to delete

        Returns:
            Number of chains deleted
        """
        query = """
        MATCH (c:CascadeChain)
        WHERE c.status = 'completed'
            AND c.completed_at IS NOT NULL
            AND datetime(c.completed_at) < datetime() - duration({days: $days_old})
        OPTIONAL MATCH (c)-[:HAS_EVENT]->(e:CascadeEvent)
        WITH c, collect(e) AS events
        DETACH DELETE c
        FOREACH (e IN events | DELETE e)
        RETURN count(c) AS deleted
        """

        result = await self.client.execute_single(query, {"days_old": days_old})

        deleted = result.get("deleted", 0) if result else 0

        if deleted > 0:
            self.logger.info(
                "cascade_chains_cleaned_up",
                deleted=deleted,
                days_old=days_old,
            )

        return deleted

    async def get_metrics(self) -> dict[str, Any]:
        """
        Get cascade repository metrics.

        Returns:
            Dictionary of metrics
        """
        query = """
        MATCH (c:CascadeChain)
        WITH c,
             CASE WHEN c.status = 'active' OR c.completed_at IS NULL THEN 1 ELSE 0 END AS is_active
        RETURN
            count(c) AS total_chains,
            sum(is_active) AS active_chains,
            sum(CASE WHEN c.status = 'completed' THEN 1 ELSE 0 END) AS completed_chains,
            sum(c.total_hops) AS total_hops,
            avg(c.total_hops) AS avg_hops_per_chain,
            sum(c.insights_generated) AS total_insights,
            sum(c.errors_encountered) AS total_errors
        """

        result = await self.client.execute_single(query, {})

        if not result:
            return {
                "total_chains": 0,
                "active_chains": 0,
                "completed_chains": 0,
                "total_hops": 0,
                "avg_hops_per_chain": 0.0,
                "total_insights": 0,
                "total_errors": 0,
            }

        return {
            "total_chains": result.get("total_chains", 0),
            "active_chains": result.get("active_chains", 0),
            "completed_chains": result.get("completed_chains", 0),
            "total_hops": result.get("total_hops", 0),
            "avg_hops_per_chain": result.get("avg_hops_per_chain", 0.0) or 0.0,
            "total_insights": result.get("total_insights", 0),
            "total_errors": result.get("total_errors", 0),
        }


# Global repository instance
_cascade_repo: CascadeRepository | None = None


def get_cascade_repository(client: Neo4jClient | None = None) -> CascadeRepository:
    """
    Get or create the cascade repository singleton.

    Args:
        client: Optional Neo4j client (required for first call)

    Returns:
        CascadeRepository instance
    """
    global _cascade_repo

    if _cascade_repo is None:
        if client is None:
            raise ValueError("Neo4j client required for first initialization")
        _cascade_repo = CascadeRepository(client)

    return _cascade_repo
