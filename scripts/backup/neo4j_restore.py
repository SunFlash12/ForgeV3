#!/usr/bin/env python3
"""
Neo4j Database Restore Script

Restores nodes and relationships from a backup JSON file.
Works with any Neo4j deployment including Aura (cloud).

CAUTION: This script will modify your database. Always verify
the backup file and target database before proceeding.

Usage:
    python neo4j_restore.py backup_file.json.gz
    python neo4j_restore.py backup_file.json.gz --dry-run
    python neo4j_restore.py backup_file.json.gz --clear-first
"""

import asyncio
import argparse
import gzip
import json
import os
import sys
from datetime import datetime, timezone
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

BATCH_SIZE = 500


class Neo4jRestore:
    """Neo4j database restore handler."""

    def __init__(
        self,
        uri: str,
        user: str,
        password: str,
        database: str = "neo4j",
    ):
        self.uri = uri
        self.user = user
        self.password = password
        self.database = database
        self._driver = None

        self.stats = {
            "nodes_created": 0,
            "relationships_created": 0,
            "errors": 0,
            "start_time": None,
            "end_time": None,
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

    async def clear_database(self) -> None:
        """Clear all data from the database. USE WITH CAUTION."""
        logger.warning("Clearing database", database=self.database)

        async with self._driver.session(database=self.database) as session:
            # Delete all relationships first
            await session.run("MATCH ()-[r]->() DELETE r")
            # Then delete all nodes
            await session.run("MATCH (n) DELETE n")

        logger.info("Database cleared")

    async def _create_node(self, session, node_data: dict) -> str | None:
        """Create a single node and return its new element ID."""
        labels = ":".join(node_data["labels"])
        props = node_data["properties"]

        # Build the query
        query = f"CREATE (n:{labels} $props) RETURN elementId(n) as id"

        try:
            result = await session.run(query, {"props": props})
            record = await result.single()
            return record["id"] if record else None
        except Exception as e:
            logger.error("Failed to create node", labels=labels, error=str(e))
            self.stats["errors"] += 1
            return None

    async def _create_nodes_batch(self, session, nodes: list[dict]) -> dict[str, str]:
        """Create nodes in batches and return ID mapping."""
        id_map = {}  # old_id -> new_id

        for i in range(0, len(nodes), BATCH_SIZE):
            batch = nodes[i:i + BATCH_SIZE]

            for node_data in batch:
                old_id = node_data["id"]
                new_id = await self._create_node(session, node_data)
                if new_id:
                    id_map[old_id] = new_id
                    self.stats["nodes_created"] += 1

            logger.info(
                "Nodes restored",
                progress=f"{min(i + BATCH_SIZE, len(nodes))}/{len(nodes)}",
            )

        return id_map

    async def _create_relationship(
        self,
        session,
        rel_data: dict,
        id_map: dict[str, str],
    ) -> bool:
        """Create a single relationship using the ID mapping."""
        start_id = id_map.get(rel_data["start_id"])
        end_id = id_map.get(rel_data["end_id"])

        if not start_id or not end_id:
            logger.warning(
                "Missing node for relationship",
                rel_type=rel_data["type"],
                start_found=bool(start_id),
                end_found=bool(end_id),
            )
            self.stats["errors"] += 1
            return False

        rel_type = rel_data["type"]
        props = rel_data["properties"]

        query = f"""
            MATCH (a), (b)
            WHERE elementId(a) = $start_id AND elementId(b) = $end_id
            CREATE (a)-[r:{rel_type} $props]->(b)
            RETURN r
        """

        try:
            result = await session.run(
                query,
                {"start_id": start_id, "end_id": end_id, "props": props},
            )
            await result.consume()
            return True
        except Exception as e:
            logger.error(
                "Failed to create relationship",
                rel_type=rel_type,
                error=str(e),
            )
            self.stats["errors"] += 1
            return False

    async def _create_relationships_batch(
        self,
        session,
        relationships: list[dict],
        id_map: dict[str, str],
    ) -> None:
        """Create relationships in batches."""
        for i in range(0, len(relationships), BATCH_SIZE):
            batch = relationships[i:i + BATCH_SIZE]

            for rel_data in batch:
                if await self._create_relationship(session, rel_data, id_map):
                    self.stats["relationships_created"] += 1

            logger.info(
                "Relationships restored",
                progress=f"{min(i + BATCH_SIZE, len(relationships))}/{len(relationships)}",
            )

    def load_backup(self, backup_path: Path) -> dict:
        """Load backup data from file."""
        logger.info("Loading backup file", path=str(backup_path))

        if backup_path.suffix == ".gz" or str(backup_path).endswith(".json.gz"):
            with gzip.open(backup_path, "rt", encoding="utf-8") as f:
                data = json.load(f)
        else:
            with open(backup_path, "r", encoding="utf-8") as f:
                data = json.load(f)

        logger.info(
            "Backup loaded",
            backup_type=data.get("metadata", {}).get("backup_type", "unknown"),
            timestamp=data.get("metadata", {}).get("timestamp", "unknown"),
            nodes=len(data.get("nodes", [])),
            relationships=len(data.get("relationships", [])),
        )

        return data

    async def restore(
        self,
        backup_path: Path,
        clear_first: bool = False,
        dry_run: bool = False,
    ) -> None:
        """
        Restore database from backup.

        Args:
            backup_path: Path to the backup file
            clear_first: If True, clear the database before restoring
            dry_run: If True, only validate backup without restoring
        """
        self.stats["start_time"] = datetime.now(timezone.utc)

        # Load backup
        backup_data = self.load_backup(backup_path)
        nodes = backup_data.get("nodes", [])
        relationships = backup_data.get("relationships", [])

        if dry_run:
            logger.info(
                "Dry run - would restore",
                nodes=len(nodes),
                relationships=len(relationships),
            )
            print(f"\nDry run summary:")
            print(f"  Backup type: {backup_data.get('metadata', {}).get('backup_type', 'unknown')}")
            print(f"  Backup date: {backup_data.get('metadata', {}).get('timestamp', 'unknown')}")
            print(f"  Nodes to restore: {len(nodes)}")
            print(f"  Relationships to restore: {len(relationships)}")
            return

        async with self._driver.session(database=self.database) as session:
            # Optionally clear database
            if clear_first:
                # SECURITY FIX (Audit 4): Require confirmation before deleting all data
                print("\n" + "=" * 60)
                print("WARNING: This will DELETE ALL DATA in the database!")
                print(f"Database: {self.database}")
                print("=" * 60)
                confirm = input("Type 'yes' to confirm deletion: ")
                if confirm.lower() != "yes":
                    logger.warning("Restore aborted by user")
                    print("Aborted. No changes made.")
                    return
                await self.clear_database()

            # Restore nodes
            logger.info("Restoring nodes", count=len(nodes))
            id_map = await self._create_nodes_batch(session, nodes)

            # Restore relationships
            logger.info("Restoring relationships", count=len(relationships))
            await self._create_relationships_batch(session, relationships, id_map)

        self.stats["end_time"] = datetime.now(timezone.utc)

        logger.info(
            "Restore completed",
            nodes_created=self.stats["nodes_created"],
            relationships_created=self.stats["relationships_created"],
            errors=self.stats["errors"],
            duration_seconds=(self.stats["end_time"] - self.stats["start_time"]).total_seconds(),
        )


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Neo4j Database Restore")
    parser.add_argument(
        "backup_file",
        type=str,
        help="Path to the backup file (JSON or JSON.GZ)",
    )
    parser.add_argument(
        "--clear-first",
        action="store_true",
        help="Clear the database before restoring (DANGEROUS)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate backup without actually restoring",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompts",
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

    backup_path = Path(args.backup_file)
    if not backup_path.exists():
        logger.error("Backup file not found", path=str(backup_path))
        sys.exit(1)

    # Confirmation for dangerous operations
    if not args.dry_run and not args.force:
        print(f"\nWARNING: This will restore data to {database} database.")
        if args.clear_first:
            print("WARNING: --clear-first will DELETE ALL EXISTING DATA first!")

        response = input("\nType 'yes' to continue: ")
        if response.lower() != "yes":
            print("Aborted.")
            sys.exit(0)

    restore = Neo4jRestore(
        uri=uri,
        user=user,
        password=password,
        database=database,
    )

    try:
        await restore.connect()
        await restore.restore(
            backup_path=backup_path,
            clear_first=args.clear_first,
            dry_run=args.dry_run,
        )

        if not args.dry_run:
            print(f"\nRestore completed:")
            print(f"  Nodes created: {restore.stats['nodes_created']}")
            print(f"  Relationships created: {restore.stats['relationships_created']}")
            print(f"  Errors: {restore.stats['errors']}")

    except Exception as e:
        logger.exception("Restore failed", error=str(e))
        sys.exit(1)
    finally:
        await restore.close()


if __name__ == "__main__":
    asyncio.run(main())
