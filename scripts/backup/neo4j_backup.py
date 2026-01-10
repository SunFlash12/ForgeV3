#!/usr/bin/env python3
"""
Neo4j Database Backup Script

Exports all nodes and relationships from Neo4j to JSON files.
Works with any Neo4j deployment including Aura (cloud).

Features:
- Full database export via Cypher queries
- Incremental backup support (by timestamp)
- Compression (gzip)
- Retention policy (configurable days to keep)
- Email/webhook notifications (optional)

Usage:
    python neo4j_backup.py                    # Full backup
    python neo4j_backup.py --incremental      # Incremental backup
    python neo4j_backup.py --retention-days 7 # Keep 7 days of backups
"""

import asyncio
import argparse
import gzip
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "forge-cascade-v2"))

import structlog
from neo4j import AsyncGraphDatabase

# Configure logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.dev.ConsoleRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

# Default configuration
DEFAULT_BACKUP_DIR = Path(__file__).parent.parent.parent / "backups" / "neo4j"
DEFAULT_RETENTION_DAYS = 30
BATCH_SIZE = 1000

# Memory threshold for warning about large databases
LARGE_DB_THRESHOLD = 100000  # Warn if > 100k nodes


class Neo4jBackup:
    """Neo4j database backup handler."""

    def __init__(
        self,
        uri: str,
        user: str,
        password: str,
        database: str = "neo4j",
        backup_dir: Path | None = None,
    ):
        self.uri = uri
        self.user = user
        self.password = password
        self.database = database
        self.backup_dir = backup_dir or DEFAULT_BACKUP_DIR
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        self._driver = None
        self.stats = {
            "nodes_exported": 0,
            "relationships_exported": 0,
            "start_time": None,
            "end_time": None,
            "backup_file": None,
            "compressed_size": 0,
        }

    async def connect(self) -> None:
        """Connect to Neo4j."""
        logger.info("Connecting to Neo4j", uri=self.uri, database=self.database)
        self._driver = AsyncGraphDatabase.driver(
            self.uri,
            auth=(self.user, self.password),
        )
        await self._driver.verify_connectivity()
        logger.info("Connected to Neo4j")

    async def close(self) -> None:
        """Close Neo4j connection."""
        if self._driver:
            await self._driver.close()
            logger.info("Neo4j connection closed")

    async def _export_nodes(self, session, since: datetime | None = None) -> list[dict]:
        """Export all nodes from the database."""
        nodes = []

        # Build query with optional timestamp filter
        if since:
            query = """
                MATCH (n)
                WHERE n.created_at >= $since OR n.updated_at >= $since
                RETURN labels(n) as labels, properties(n) as props, elementId(n) as id
            """
            params = {"since": since.isoformat()}
        else:
            query = """
                MATCH (n)
                RETURN labels(n) as labels, properties(n) as props, elementId(n) as id
            """
            params = {}

        result = await session.run(query, params)

        async for record in result:
            node_data = {
                "id": record["id"],
                "labels": record["labels"],
                "properties": self._serialize_properties(record["props"]),
            }
            nodes.append(node_data)
            self.stats["nodes_exported"] += 1

            if self.stats["nodes_exported"] % 1000 == 0:
                logger.info("Nodes exported", count=self.stats["nodes_exported"])

        return nodes

    async def _export_relationships(self, session, since: datetime | None = None) -> list[dict]:
        """Export all relationships from the database."""
        relationships = []

        # Build query with optional timestamp filter
        if since:
            query = """
                MATCH (a)-[r]->(b)
                WHERE r.created_at >= $since OR r.updated_at >= $since
                RETURN type(r) as type, properties(r) as props,
                       elementId(r) as id, elementId(a) as start_id, elementId(b) as end_id
            """
            params = {"since": since.isoformat()}
        else:
            query = """
                MATCH (a)-[r]->(b)
                RETURN type(r) as type, properties(r) as props,
                       elementId(r) as id, elementId(a) as start_id, elementId(b) as end_id
            """
            params = {}

        result = await session.run(query, params)

        async for record in result:
            rel_data = {
                "id": record["id"],
                "type": record["type"],
                "start_id": record["start_id"],
                "end_id": record["end_id"],
                "properties": self._serialize_properties(record["props"]),
            }
            relationships.append(rel_data)
            self.stats["relationships_exported"] += 1

            if self.stats["relationships_exported"] % 1000 == 0:
                logger.info("Relationships exported", count=self.stats["relationships_exported"])

        return relationships

    def _serialize_properties(self, props: dict) -> dict:
        """Serialize properties to JSON-compatible format."""
        serialized = {}
        for key, value in props.items():
            if isinstance(value, (datetime,)):
                serialized[key] = value.isoformat()
            elif isinstance(value, (list, tuple)):
                serialized[key] = [
                    v.isoformat() if isinstance(v, datetime) else v
                    for v in value
                ]
            else:
                serialized[key] = value
        return serialized

    async def _get_database_info(self, session) -> dict:
        """Get database metadata."""
        result = await session.run(
            "CALL dbms.components() YIELD name, versions, edition "
            "RETURN name, versions, edition"
        )
        record = await result.single()

        # Get counts
        node_count_result = await session.run("MATCH (n) RETURN count(n) as count")
        node_count = (await node_count_result.single())["count"]

        rel_count_result = await session.run("MATCH ()-[r]->() RETURN count(r) as count")
        rel_count = (await rel_count_result.single())["count"]

        return {
            "name": record["name"] if record else "unknown",
            "version": record["versions"][0] if record and record["versions"] else "unknown",
            "edition": record["edition"] if record else "unknown",
            "node_count": node_count,
            "relationship_count": rel_count,
        }

    async def backup(self, incremental: bool = False, since: datetime | None = None) -> Path:
        """
        Perform database backup.

        Args:
            incremental: If True, only backup changes since last backup
            since: For incremental, backup changes since this timestamp

        Returns:
            Path to the backup file
        """
        self.stats["start_time"] = datetime.now(timezone.utc)

        async with self._driver.session(database=self.database) as session:
            # Get database info
            db_info = await self._get_database_info(session)

            # Memory warning for large databases
            total_objects = db_info["node_count"] + db_info["relationship_count"]
            if total_objects > LARGE_DB_THRESHOLD:
                logger.warning(
                    "large_database_backup",
                    node_count=db_info["node_count"],
                    rel_count=db_info["relationship_count"],
                    hint="Consider using Neo4j's native neo4j-admin dump for very large databases",
                )

            logger.info(
                "Starting backup",
                database=self.database,
                incremental=incremental,
                db_info=db_info,
            )

            # Export data
            # Note: For very large databases (1M+ nodes), consider streaming to file
            # instead of collecting in memory. This implementation is suitable for
            # databases up to ~500k nodes on systems with adequate RAM.
            nodes = await self._export_nodes(session, since if incremental else None)
            relationships = await self._export_relationships(session, since if incremental else None)

        # Prepare backup data
        backup_data = {
            "metadata": {
                "backup_type": "incremental" if incremental else "full",
                "timestamp": self.stats["start_time"].isoformat(),
                "database": self.database,
                "database_info": db_info,
                "since": since.isoformat() if since else None,
            },
            "nodes": nodes,
            "relationships": relationships,
            "stats": {
                "nodes_exported": self.stats["nodes_exported"],
                "relationships_exported": self.stats["relationships_exported"],
            },
        }

        # Generate filename
        timestamp = self.stats["start_time"].strftime("%Y%m%d_%H%M%S")
        backup_type = "incremental" if incremental else "full"
        filename = f"neo4j_backup_{backup_type}_{timestamp}.json.gz"
        backup_path = self.backup_dir / filename

        # Write compressed backup
        logger.info("Writing backup file", path=str(backup_path))
        with gzip.open(backup_path, "wt", encoding="utf-8") as f:
            json.dump(backup_data, f, indent=2, default=str)

        self.stats["end_time"] = datetime.now(timezone.utc)
        self.stats["backup_file"] = str(backup_path)
        self.stats["compressed_size"] = backup_path.stat().st_size

        logger.info(
            "Backup completed",
            file=str(backup_path),
            nodes=self.stats["nodes_exported"],
            relationships=self.stats["relationships_exported"],
            size_mb=round(self.stats["compressed_size"] / (1024 * 1024), 2),
            duration_seconds=(self.stats["end_time"] - self.stats["start_time"]).total_seconds(),
        )

        return backup_path

    def apply_retention_policy(self, retention_days: int = DEFAULT_RETENTION_DAYS) -> list[Path]:
        """
        Remove backups older than retention period.

        Args:
            retention_days: Number of days to keep backups

        Returns:
            List of deleted backup files
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        deleted = []

        for backup_file in self.backup_dir.glob("neo4j_backup_*.json.gz"):
            file_time = datetime.fromtimestamp(backup_file.stat().st_mtime, tz=timezone.utc)
            if file_time < cutoff:
                logger.info("Deleting old backup", file=str(backup_file), age_days=(datetime.now(timezone.utc) - file_time).days)
                backup_file.unlink()
                deleted.append(backup_file)

        if deleted:
            logger.info("Retention policy applied", deleted_count=len(deleted), retention_days=retention_days)
        else:
            logger.info("No old backups to delete", retention_days=retention_days)

        return deleted

    def get_last_backup_time(self) -> datetime | None:
        """Get timestamp of the most recent backup."""
        backups = sorted(
            self.backup_dir.glob("neo4j_backup_*.json.gz"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if backups:
            return datetime.fromtimestamp(backups[0].stat().st_mtime, tz=timezone.utc)
        return None


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Neo4j Database Backup")
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="Perform incremental backup (only changes since last backup)",
    )
    parser.add_argument(
        "--retention-days",
        type=int,
        default=DEFAULT_RETENTION_DAYS,
        help=f"Number of days to keep backups (default: {DEFAULT_RETENTION_DAYS})",
    )
    parser.add_argument(
        "--backup-dir",
        type=str,
        default=str(DEFAULT_BACKUP_DIR),
        help=f"Directory to store backups (default: {DEFAULT_BACKUP_DIR})",
    )
    parser.add_argument(
        "--no-retention",
        action="store_true",
        help="Skip retention policy (keep all backups)",
    )
    args = parser.parse_args()

    # Get credentials from environment
    uri = os.environ.get("NEO4J_URI")
    user = os.environ.get("NEO4J_USERNAME", os.environ.get("NEO4J_USER"))
    password = os.environ.get("NEO4J_PASSWORD")
    database = os.environ.get("NEO4J_DATABASE", "neo4j")

    if not all([uri, user, password]):
        logger.error(
            "Missing required environment variables",
            required=["NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD"],
        )
        sys.exit(1)

    backup = Neo4jBackup(
        uri=uri,
        user=user,
        password=password,
        database=database,
        backup_dir=Path(args.backup_dir),
    )

    try:
        await backup.connect()

        # Determine incremental since time
        since = None
        if args.incremental:
            since = backup.get_last_backup_time()
            if since:
                logger.info("Incremental backup since", timestamp=since.isoformat())
            else:
                logger.warning("No previous backup found, performing full backup")

        # Perform backup
        backup_path = await backup.backup(
            incremental=args.incremental and since is not None,
            since=since,
        )

        # Apply retention policy
        if not args.no_retention:
            backup.apply_retention_policy(args.retention_days)

        print(f"\nBackup completed: {backup_path}")
        print(f"Nodes: {backup.stats['nodes_exported']}")
        print(f"Relationships: {backup.stats['relationships_exported']}")
        print(f"Size: {round(backup.stats['compressed_size'] / (1024 * 1024), 2)} MB")

    except Exception as e:
        logger.exception("Backup failed", error=str(e))
        sys.exit(1)
    finally:
        await backup.close()


if __name__ == "__main__":
    asyncio.run(main())
