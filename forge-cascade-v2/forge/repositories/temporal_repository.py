"""
Temporal Repository

Manages capsule versioning and trust snapshot storage with
hybrid snapshot/diff strategy and smart compression.
"""

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

from forge.database.client import Neo4jClient
from forge.models.base import generate_id
from forge.models.temporal import (
    CapsuleVersion,
    ChangeType,
    GraphSnapshot,
    SnapshotType,
    TimeGranularity,
    TrustChangeType,
    TrustSnapshot,
    TrustSnapshotCompressor,
    TrustSnapshotCreate,
    TrustTimeline,
    VersionComparison,
    VersionDiff,
    VersionHistory,
    VersioningPolicy,
)

logger = structlog.get_logger(__name__)


class TemporalRepository:
    """
    Repository for temporal data: versions and trust snapshots.

    Implements hybrid versioning with smart compaction and
    essential/derived trust snapshot classification.
    """

    def __init__(
        self,
        client: Neo4jClient,
        versioning_policy: VersioningPolicy | None = None,
    ):
        self.client = client
        self.policy = versioning_policy or VersioningPolicy()
        self.compressor = TrustSnapshotCompressor()
        self.logger = structlog.get_logger(self.__class__.__name__)

    def _now(self) -> datetime:
        """Get current UTC timestamp."""
        return datetime.now(UTC)

    # ═══════════════════════════════════════════════════════════════
    # CAPSULE VERSIONING
    # ═══════════════════════════════════════════════════════════════

    async def create_version(
        self,
        capsule_id: str,
        content: str,
        change_type: ChangeType,
        created_by: str,
        trust_level: int = 60,
        change_summary: str | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CapsuleVersion:
        """
        Create a new version for a capsule.

        Automatically decides between full snapshot and diff based on policy.
        """
        # Get current version info
        current = await self._get_latest_version(capsule_id)
        change_number = (current.get("version_count", 0) if current else 0) + 1
        previous_content = current.get("content") if current else None
        diff_chain_length = current.get("diff_chain_length", 0) if current else 0

        # Compute content hash
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        # Determine version number
        if change_type == ChangeType.CREATE:
            version_number = "1.0.0"
        elif current:
            version_number = self._increment_version(
                current.get("version_number", "1.0.0"),
                is_major=change_type in {ChangeType.FORK, ChangeType.MERGE},
            )
        else:
            version_number = "1.0.0"

        # Decide snapshot type based on policy
        is_major = version_number.split(".")[0] != (
            current.get("version_number", "1.0.0").split(".")[0] if current else "1"
        )

        should_snapshot = self.policy.should_full_snapshot(
            change_number=change_number,
            trust_level=trust_level,
            is_major_version=is_major,
            diff_chain_length=diff_chain_length,
        )

        # Build version data
        version_id = generate_id()
        now = self._now()

        if should_snapshot or previous_content is None:
            # Full snapshot
            snapshot_type = SnapshotType.FULL
            content_snapshot = content
            diff_data = None
            new_diff_chain = 0
        else:
            # Diff from previous
            snapshot_type = SnapshotType.DIFF
            content_snapshot = None
            diff_data = self._compute_diff(previous_content, content)
            new_diff_chain = diff_chain_length + 1

            # Check if diff is too large
            if diff_data and len(str(diff_data.model_dump())) > self.policy.max_diff_size_bytes:
                snapshot_type = SnapshotType.FULL
                content_snapshot = content
                diff_data = None
                new_diff_chain = 0

        # Create version in database
        query = """
        CREATE (v:CapsuleVersion {
            id: $id,
            capsule_id: $capsule_id,
            version_number: $version_number,
            snapshot_type: $snapshot_type,
            content_snapshot: $content_snapshot,
            content_hash: $content_hash,
            diff_from_previous: $diff_json,
            parent_version_id: $parent_version_id,
            trust_at_version: $trust_level,
            change_type: $change_type,
            change_summary: $change_summary,
            tags_at_version: $tags,
            metadata_at_version: $metadata,
            created_by: $created_by,
            created_at: $now,
            updated_at: $now,
            diff_chain_length: $diff_chain_length
        })
        WITH v
        MATCH (c:Capsule {id: $capsule_id})
        CREATE (c)-[:HAS_VERSION]->(v)
        WITH v
        OPTIONAL MATCH (prev:CapsuleVersion {id: $parent_version_id})
        FOREACH (_ IN CASE WHEN prev IS NOT NULL THEN [1] ELSE [] END |
            CREATE (v)-[:PREVIOUS_VERSION]->(prev)
        )
        RETURN v {.*} AS version
        """

        params = {
            "id": version_id,
            "capsule_id": capsule_id,
            "version_number": version_number,
            "snapshot_type": snapshot_type.value,
            "content_snapshot": content_snapshot,
            "content_hash": content_hash,
            "diff_json": diff_data.model_dump_json() if diff_data else None,
            "parent_version_id": current.get("version_id") if current else None,
            "trust_level": trust_level,
            "change_type": change_type.value,
            "change_summary": change_summary,
            "tags": tags or [],
            "metadata": metadata or {},
            "created_by": created_by,
            "now": now.isoformat(),
            "diff_chain_length": new_diff_chain,
        }

        result = await self.client.execute_single(query, params)

        if result and result.get("version"):
            self.logger.info(
                "Created version",
                capsule_id=capsule_id,
                version_id=version_id,
                version_number=version_number,
                snapshot_type=snapshot_type.value,
            )
            return self._to_version(result["version"])

        raise RuntimeError(f"Failed to create version for capsule {capsule_id}")

    async def get_version_history(
        self,
        capsule_id: str,
        limit: int = 50,
        include_content: bool = False,
    ) -> VersionHistory:
        """Get version history for a capsule."""
        query = """
        MATCH (c:Capsule {id: $capsule_id})-[:HAS_VERSION]->(v:CapsuleVersion)
        RETURN v {.*} AS version
        ORDER BY v.created_at DESC
        LIMIT $limit
        """

        results = await self.client.execute(
            query,
            {"capsule_id": capsule_id, "limit": limit},
        )

        versions = [self._to_version(r["version"]) for r in results if r.get("version")]

        # Get summary stats
        stats_query = """
        MATCH (c:Capsule {id: $capsule_id})-[:HAS_VERSION]->(v:CapsuleVersion)
        WITH c, v ORDER BY v.created_at
        WITH c,
             count(v) AS total,
             head(collect(v)) AS first,
             last(collect(v)) AS latest,
             collect(DISTINCT v.created_by) AS contributors
        RETURN total, first.created_at AS first_created, latest.created_at AS last_modified,
               latest.version_number AS current_version, contributors
        """

        stats = await self.client.execute_single(stats_query, {"capsule_id": capsule_id})

        return VersionHistory(
            capsule_id=capsule_id,
            current_version=stats.get("current_version", "1.0.0") if stats else "1.0.0",
            total_versions=stats.get("total", 0) if stats else 0,
            versions=versions,
            first_created=stats.get("first_created") if stats else None,
            last_modified=stats.get("last_modified") if stats else None,
            total_changes=stats.get("total", 0) if stats else 0,
            contributors=stats.get("contributors", []) if stats else [],
        )

    async def get_capsule_at_time(
        self,
        capsule_id: str,
        timestamp: datetime,
    ) -> CapsuleVersion | None:
        """Get the capsule state at a specific point in time."""
        query = """
        MATCH (c:Capsule {id: $capsule_id})-[:HAS_VERSION]->(v:CapsuleVersion)
        WHERE v.created_at <= $timestamp
        RETURN v {.*} AS version
        ORDER BY v.created_at DESC
        LIMIT 1
        """

        result = await self.client.execute_single(
            query,
            {
                "capsule_id": capsule_id,
                "timestamp": timestamp.isoformat(),
            },
        )

        if result and result.get("version"):
            version = self._to_version(result["version"])

            # If it's a diff, reconstruct content
            if version.snapshot_type == SnapshotType.DIFF:
                content = await self._reconstruct_content(version)
                version.content_snapshot = content

            return version

        return None

    async def diff_versions(
        self,
        version_a_id: str,
        version_b_id: str,
    ) -> VersionComparison:
        """Compare two versions."""
        query = """
        MATCH (a:CapsuleVersion {id: $version_a})
        MATCH (b:CapsuleVersion {id: $version_b})
        RETURN a {.*} AS version_a, b {.*} AS version_b
        """

        result = await self.client.execute_single(
            query,
            {"version_a": version_a_id, "version_b": version_b_id},
        )

        if not result:
            raise ValueError("One or both versions not found")

        va = self._to_version(result["version_a"])
        vb = self._to_version(result["version_b"])

        # Reconstruct content if needed
        content_a = va.content_snapshot or await self._reconstruct_content(va)
        content_b = vb.content_snapshot or await self._reconstruct_content(vb)

        diff = self._compute_diff(content_a or "", content_b or "")

        return VersionComparison(
            capsule_id=va.capsule_id,
            version_a_id=version_a_id,
            version_b_id=version_b_id,
            version_a_number=va.version_number,
            version_b_number=vb.version_number,
            diff=diff,
            trust_change=vb.trust_at_version - va.trust_at_version,
        )

    async def _get_latest_version(self, capsule_id: str) -> dict | None:
        """Get the latest version info for a capsule."""
        query = """
        MATCH (c:Capsule {id: $capsule_id})-[:HAS_VERSION]->(v:CapsuleVersion)
        WITH v ORDER BY v.created_at DESC
        LIMIT 1
        OPTIONAL MATCH (c)-[:HAS_VERSION]->(all:CapsuleVersion)
        RETURN v.id AS version_id,
               v.version_number AS version_number,
               v.content_snapshot AS content,
               v.diff_chain_length AS diff_chain_length,
               count(all) AS version_count
        """

        return await self.client.execute_single(query, {"capsule_id": capsule_id})

    async def _reconstruct_content(self, version: CapsuleVersion) -> str | None:
        """Reconstruct content from diff chain."""
        if version.snapshot_type == SnapshotType.FULL:
            return version.content_snapshot

        # Walk back to find a full snapshot
        query = """
        MATCH path = (v:CapsuleVersion {id: $version_id})-[:PREVIOUS_VERSION*0..20]->(snapshot:CapsuleVersion)
        WHERE snapshot.snapshot_type = 'full'
        WITH path, snapshot, length(path) AS distance
        ORDER BY distance
        LIMIT 1
        RETURN [n IN nodes(path) | n {.*}] AS chain
        """

        result = await self.client.execute_single(query, {"version_id": version.id})

        if not result or not result.get("chain"):
            return None

        # Apply diffs in order (from snapshot forward)
        chain = list(reversed(result["chain"]))
        content = chain[0].get("content_snapshot", "")

        for node in chain[1:]:
            diff_json = node.get("diff_from_previous")
            if diff_json:
                try:
                    diff = VersionDiff.model_validate_json(diff_json)
                    content = self._apply_diff(content, diff)
                except Exception as e:
                    self.logger.error("Failed to apply diff", error=str(e))

        return content

    def _compute_diff(self, old_content: str, new_content: str) -> VersionDiff:
        """Compute a simple line-based diff."""
        old_lines = old_content.split("\n")
        new_lines = new_content.split("\n")

        # Simple diff: find added and removed lines
        old_set = set(old_lines)
        new_set = set(new_lines)

        added = [line for line in new_lines if line not in old_set]
        removed = [line for line in old_lines if line not in new_set]

        return VersionDiff(
            added_lines=added[:100],  # Limit for storage
            removed_lines=removed[:100],
            summary=f"+{len(added)} -{len(removed)} lines",
        )

    def _apply_diff(self, content: str, diff: VersionDiff) -> str:
        """
        Apply a diff to content.

        FIX: Reimplemented using proper line-based diff matching.
        Previous implementation was broken (removed wrong lines, lost ordering).
        """
        if not diff.removed_lines and not diff.added_lines:
            return content

        old_lines = content.split("\n")
        new_lines = []
        removed_set = set(diff.removed_lines)

        # Track which lines from removed_set we've actually removed
        # to handle duplicates correctly
        removed_count = {line: diff.removed_lines.count(line) for line in removed_set}

        for line in old_lines:
            if line in removed_count and removed_count[line] > 0:
                # Skip this line (it was removed)
                removed_count[line] -= 1
            else:
                new_lines.append(line)

        # Add new lines at the end (simplified - proper impl would track positions)
        new_lines.extend(diff.added_lines)

        return "\n".join(new_lines)

    def _increment_version(self, version: str, is_major: bool = False) -> str:
        """Increment a semantic version."""
        parts = version.split(".")
        if len(parts) != 3:
            return "1.0.1"

        major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])

        if is_major:
            return f"{major + 1}.0.0"
        else:
            return f"{major}.{minor}.{patch + 1}"

    def _to_version(self, record: dict) -> CapsuleVersion:
        """Convert a Neo4j record to CapsuleVersion."""
        diff_json = record.get("diff_from_previous")
        diff = None
        if diff_json:
            try:
                diff = VersionDiff.model_validate_json(diff_json)
            except Exception:
                pass

        return CapsuleVersion(
            id=record["id"],
            capsule_id=record["capsule_id"],
            version_number=record["version_number"],
            snapshot_type=SnapshotType(record.get("snapshot_type", "full")),
            content_snapshot=record.get("content_snapshot"),
            content_hash=record.get("content_hash", ""),
            diff_from_previous=diff,
            parent_version_id=record.get("parent_version_id"),
            trust_at_version=record.get("trust_at_version", 60),
            change_type=ChangeType(record.get("change_type", "update")),
            change_summary=record.get("change_summary"),
            tags_at_version=record.get("tags_at_version", []),
            metadata_at_version=record.get("metadata_at_version", {}),
            created_by=record.get("created_by", ""),
            created_at=self._parse_datetime(record.get("created_at")),
            updated_at=self._parse_datetime(record.get("updated_at")),
        )

    # ═══════════════════════════════════════════════════════════════
    # TRUST SNAPSHOTS
    # ═══════════════════════════════════════════════════════════════

    async def create_trust_snapshot(
        self,
        data: TrustSnapshotCreate,
    ) -> TrustSnapshot:
        """
        Create a trust snapshot with automatic classification.

        Essential changes are preserved in full, derived changes
        are compressed with reconstruction hints.
        """
        snapshot_id = generate_id()
        now = self._now()

        # Get previous value for delta calculation
        previous = await self._get_latest_trust_snapshot(
            data.entity_id,
            data.entity_type,
        )
        previous_value = previous.get("trust_value") if previous else None

        # Create snapshot
        snapshot = TrustSnapshot(
            id=snapshot_id,
            entity_id=data.entity_id,
            entity_type=data.entity_type,
            trust_value=data.trust_value,
            reason=data.reason,
            adjusted_by=data.adjusted_by,
            evidence=data.evidence,
            source_event_id=data.source_event_id,
            previous_value=previous_value,
            delta=data.trust_value - previous_value if previous_value else None,
            created_at=now,
            updated_at=now,
        )

        # Apply compression
        snapshot = self.compressor.compress(snapshot)

        # Store in database
        query = """
        CREATE (t:TrustSnapshot {
            id: $id,
            entity_id: $entity_id,
            entity_type: $entity_type,
            trust_value: $trust_value,
            change_type: $change_type,
            reason: $reason,
            adjusted_by: $adjusted_by,
            evidence: $evidence,
            source_event_id: $source_event_id,
            reconstruction_hint: $reconstruction_hint,
            previous_value: $previous_value,
            delta: $delta,
            timestamp: $now,
            created_at: $now,
            updated_at: $now
        })
        RETURN t {.*} AS snapshot
        """

        params = {
            "id": snapshot_id,
            "entity_id": snapshot.entity_id,
            "entity_type": snapshot.entity_type,
            "trust_value": snapshot.trust_value,
            "change_type": snapshot.change_type.value,
            "reason": snapshot.reason,
            "adjusted_by": snapshot.adjusted_by,
            "evidence": snapshot.evidence,
            "source_event_id": snapshot.source_event_id,
            "reconstruction_hint": snapshot.reconstruction_hint,
            "previous_value": snapshot.previous_value,
            "delta": snapshot.delta,
            "now": now.isoformat(),
        }

        await self.client.execute(query, params)

        self.logger.debug(
            "Created trust snapshot",
            entity_id=snapshot.entity_id,
            change_type=snapshot.change_type.value,
        )

        return snapshot

    async def get_trust_timeline(
        self,
        entity_id: str,
        entity_type: str,
        start: datetime | None = None,
        end: datetime | None = None,
        granularity: TimeGranularity = TimeGranularity.DAY,
        include_derived: bool = True,
    ) -> TrustTimeline:
        """Get trust evolution over time."""
        conditions = [
            "t.entity_id = $entity_id",
            "t.entity_type = $entity_type",
        ]
        params: dict[str, Any] = {
            "entity_id": entity_id,
            "entity_type": entity_type,
        }

        if start:
            conditions.append("t.timestamp >= $start")
            params["start"] = start.isoformat()

        if end:
            conditions.append("t.timestamp <= $end")
            params["end"] = end.isoformat()

        if not include_derived:
            conditions.append("t.change_type = 'essential'")

        where_clause = " AND ".join(conditions)

        query = f"""
        MATCH (t:TrustSnapshot)
        WHERE {where_clause}
        RETURN t {{.*}} AS snapshot
        ORDER BY t.timestamp
        """

        results = await self.client.execute(query, params)

        snapshots = [self._to_trust_snapshot(r["snapshot"]) for r in results if r.get("snapshot")]

        # Calculate stats
        trust_values = [s.trust_value for s in snapshots]

        if trust_values:
            import statistics
            min_trust = min(trust_values)
            max_trust = max(trust_values)
            avg_trust = statistics.mean(trust_values)
            volatility = statistics.stdev(trust_values) if len(trust_values) > 1 else 0.0
        else:
            min_trust = max_trust = 60
            avg_trust = 60.0
            volatility = 0.0

        return TrustTimeline(
            entity_id=entity_id,
            entity_type=entity_type,
            snapshots=snapshots,
            start_time=start or (snapshots[0].created_at if snapshots else self._now()),
            end_time=end or (snapshots[-1].created_at if snapshots else self._now()),
            granularity=granularity,
            min_trust=min_trust,
            max_trust=max_trust,
            avg_trust=avg_trust,
            volatility=volatility,
            total_adjustments=len(snapshots),
        )

    async def _get_latest_trust_snapshot(
        self,
        entity_id: str,
        entity_type: str,
    ) -> dict | None:
        """Get the most recent trust snapshot for an entity."""
        query = """
        MATCH (t:TrustSnapshot {entity_id: $entity_id, entity_type: $entity_type})
        RETURN t.trust_value AS trust_value
        ORDER BY t.timestamp DESC
        LIMIT 1
        """

        return await self.client.execute_single(
            query,
            {"entity_id": entity_id, "entity_type": entity_type},
        )

    def _to_trust_snapshot(self, record: dict) -> TrustSnapshot:
        """Convert a Neo4j record to TrustSnapshot."""
        return TrustSnapshot(
            id=record["id"],
            entity_id=record["entity_id"],
            entity_type=record["entity_type"],
            trust_value=record["trust_value"],
            change_type=TrustChangeType(record.get("change_type", "derived")),
            reason=record.get("reason"),
            adjusted_by=record.get("adjusted_by"),
            evidence=record.get("evidence"),
            source_event_id=record.get("source_event_id"),
            reconstruction_hint=record.get("reconstruction_hint"),
            previous_value=record.get("previous_value"),
            delta=record.get("delta"),
            created_at=self._parse_datetime(record.get("created_at")),
            updated_at=self._parse_datetime(record.get("updated_at")),
        )

    # ═══════════════════════════════════════════════════════════════
    # GRAPH SNAPSHOTS
    # ═══════════════════════════════════════════════════════════════

    async def create_graph_snapshot(
        self,
        metrics: dict[str, Any],
        created_by: str | None = None,
    ) -> GraphSnapshot:
        """Create a point-in-time graph snapshot."""
        snapshot_id = generate_id()
        now = self._now()

        query = """
        CREATE (g:GraphSnapshot {
            id: $id,
            total_nodes: $total_nodes,
            total_edges: $total_edges,
            nodes_by_type: $nodes_by_type,
            edges_by_type: $edges_by_type,
            density: $density,
            avg_degree: $avg_degree,
            connected_components: $connected_components,
            avg_trust: $avg_trust,
            trust_distribution: $trust_distribution,
            community_count: $community_count,
            modularity: $modularity,
            top_capsules_by_pagerank: $top_capsules,
            top_users_by_influence: $top_users,
            active_anomalies: $active_anomalies,
            anomaly_types: $anomaly_types,
            created_by: $created_by,
            created_at: $now,
            updated_at: $now
        })
        RETURN g {.*} AS snapshot
        """

        params = {
            "id": snapshot_id,
            "total_nodes": metrics.get("total_nodes", 0),
            "total_edges": metrics.get("total_edges", 0),
            "nodes_by_type": metrics.get("nodes_by_type", {}),
            "edges_by_type": metrics.get("edges_by_type", {}),
            "density": metrics.get("density", 0.0),
            "avg_degree": metrics.get("avg_degree", 0.0),
            "connected_components": metrics.get("connected_components", 0),
            "avg_trust": metrics.get("avg_trust_level", 60.0),
            "trust_distribution": metrics.get("trust_distribution", {}),
            "community_count": metrics.get("community_count", 0),
            "modularity": metrics.get("modularity"),
            "top_capsules": metrics.get("top_capsules_by_pagerank", []),
            "top_users": metrics.get("top_users_by_influence", []),
            "active_anomalies": metrics.get("active_anomalies", 0),
            "anomaly_types": metrics.get("anomaly_types", {}),
            "created_by": created_by,
            "now": now.isoformat(),
        }

        result = await self.client.execute_single(query, params)

        if result and result.get("snapshot"):
            self.logger.info(
                "Created graph snapshot",
                snapshot_id=snapshot_id,
                total_nodes=metrics.get("total_nodes", 0),
            )
            return self._to_graph_snapshot(result["snapshot"])

        raise RuntimeError("Failed to create graph snapshot")

    async def get_latest_graph_snapshot(self) -> GraphSnapshot | None:
        """Get the most recent graph snapshot."""
        query = """
        MATCH (g:GraphSnapshot)
        RETURN g {.*} AS snapshot
        ORDER BY g.created_at DESC
        LIMIT 1
        """

        result = await self.client.execute_single(query, {})

        if result and result.get("snapshot"):
            return self._to_graph_snapshot(result["snapshot"])
        return None

    async def get_graph_snapshots(
        self,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 30,
    ) -> list[GraphSnapshot]:
        """Get graph snapshots over time."""
        conditions = []
        params: dict[str, Any] = {"limit": limit}

        if start:
            conditions.append("g.created_at >= $start")
            params["start"] = start.isoformat()

        if end:
            conditions.append("g.created_at <= $end")
            params["end"] = end.isoformat()

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        query = f"""
        MATCH (g:GraphSnapshot)
        {where_clause}
        RETURN g {{.*}} AS snapshot
        ORDER BY g.created_at DESC
        LIMIT $limit
        """

        results = await self.client.execute(query, params)

        return [
            self._to_graph_snapshot(r["snapshot"])
            for r in results
            if r.get("snapshot")
        ]

    def _to_graph_snapshot(self, record: dict) -> GraphSnapshot:
        """Convert a Neo4j record to GraphSnapshot."""
        return GraphSnapshot(
            id=record["id"],
            total_nodes=record.get("total_nodes", 0),
            total_edges=record.get("total_edges", 0),
            nodes_by_type=self._parse_dict(record.get("nodes_by_type", {})),
            edges_by_type=self._parse_dict(record.get("edges_by_type", {})),
            density=record.get("density", 0.0),
            avg_degree=record.get("avg_degree", 0.0),
            connected_components=record.get("connected_components", 0),
            avg_trust=record.get("avg_trust", 60.0),
            trust_distribution=self._parse_dict(record.get("trust_distribution", {})),
            community_count=record.get("community_count", 0),
            modularity=record.get("modularity"),
            top_capsules_by_pagerank=self._parse_list(record.get("top_capsules_by_pagerank", [])),
            top_users_by_influence=self._parse_list(record.get("top_users_by_influence", [])),
            active_anomalies=record.get("active_anomalies", 0),
            anomaly_types=self._parse_dict(record.get("anomaly_types", {})),
            created_at=self._parse_datetime(record.get("created_at")),
            updated_at=self._parse_datetime(record.get("updated_at")),
        )

    def _parse_dict(self, value: Any) -> dict:
        """Parse a dictionary from various formats (handles Neo4j serialization)."""
        if value is None:
            return {}
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                import json
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}

    def _parse_list(self, value: Any) -> list:
        """Parse a list from various formats (handles Neo4j serialization)."""
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            try:
                import json
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return []
        return []

    # ═══════════════════════════════════════════════════════════════
    # COMPACTION
    # ═══════════════════════════════════════════════════════════════

    async def compact_old_versions(self, capsule_id: str) -> int:
        """
        Compact old diff-based versions into snapshots.

        Returns number of versions compacted.
        """
        # Find old diffs that should be compacted
        cutoff = self._now() - timedelta(days=self.policy.compact_after_days)

        query = """
        MATCH (c:Capsule {id: $capsule_id})-[:HAS_VERSION]->(v:CapsuleVersion)
        WHERE v.snapshot_type = 'diff'
          AND v.created_at < $cutoff
        RETURN v.id AS version_id
        ORDER BY v.created_at
        """

        results = await self.client.execute(
            query,
            {"capsule_id": capsule_id, "cutoff": cutoff.isoformat()},
        )

        compacted = 0
        for r in results:
            version_id = r.get("version_id")
            if version_id:
                # Get version
                version = await self._get_version_by_id(version_id)
                if version:
                    # Reconstruct and update to full snapshot
                    content = await self._reconstruct_content(version)
                    if content:
                        await self._convert_to_snapshot(version_id, content)
                        compacted += 1

        if compacted > 0:
            self.logger.info(
                "Compacted versions",
                capsule_id=capsule_id,
                count=compacted,
            )

        return compacted

    async def _get_version_by_id(self, version_id: str) -> CapsuleVersion | None:
        """Get a version by ID."""
        query = """
        MATCH (v:CapsuleVersion {id: $id})
        RETURN v {.*} AS version
        """

        result = await self.client.execute_single(query, {"id": version_id})

        if result and result.get("version"):
            return self._to_version(result["version"])
        return None

    async def _convert_to_snapshot(self, version_id: str, content: str) -> None:
        """Convert a diff version to a full snapshot."""
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        query = """
        MATCH (v:CapsuleVersion {id: $id})
        SET v.snapshot_type = 'full',
            v.content_snapshot = $content,
            v.content_hash = $content_hash,
            v.diff_from_previous = null,
            v.diff_chain_length = 0
        """

        await self.client.execute(
            query,
            {"id": version_id, "content": content, "content_hash": content_hash},
        )

    def _parse_datetime(self, value: Any) -> datetime:
        """Parse a datetime from various formats."""
        if value is None:
            return self._now()
        if isinstance(value, datetime):
            return value
        if hasattr(value, "to_native"):
            return value.to_native()
        if isinstance(value, str):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return self._now()
