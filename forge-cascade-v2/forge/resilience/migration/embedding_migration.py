"""
Embedding Migration Service
===========================

Background service for migrating capsule embeddings between model versions.
Supports batch processing, progress tracking, and rollback capabilities.
"""

from __future__ import annotations

import asyncio
import secrets
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import structlog

from forge.database.client import get_db_client
from forge.resilience.config import get_resilience_config
from forge.resilience.migration.version_registry import (
    get_version_registry,
)

logger = structlog.get_logger(__name__)


class MigrationStatus(Enum):
    """Status of a migration job."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ROLLING_BACK = "rolling_back"


@dataclass
class MigrationProgress:
    """Progress tracking for a migration job."""

    total_capsules: int = 0
    processed_capsules: int = 0
    failed_capsules: int = 0
    skipped_capsules: int = 0
    current_batch: int = 0
    total_batches: int = 0

    @property
    def percent_complete(self) -> float:
        """Get completion percentage."""
        if self.total_capsules == 0:
            return 0.0
        return (self.processed_capsules / self.total_capsules) * 100

    @property
    def success_rate(self) -> float:
        """Get success rate."""
        processed = self.processed_capsules + self.failed_capsules
        if processed == 0:
            return 100.0
        return (self.processed_capsules / processed) * 100


@dataclass
class MigrationJob:
    """Represents a migration job."""

    job_id: str
    from_version: str
    to_version: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    status: MigrationStatus = MigrationStatus.PENDING
    progress: MigrationProgress = field(default_factory=MigrationProgress)
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    # Filtering
    capsule_filter: dict[str, Any] | None = None

    # Configuration
    batch_size: int = 100
    delay_between_batches: float = 1.0
    max_retries: int = 3
    cleanup_old: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "job_id": self.job_id,
            "from_version": self.from_version,
            "to_version": self.to_version,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "status": self.status.value,
            "progress": {
                "total_capsules": self.progress.total_capsules,
                "processed_capsules": self.progress.processed_capsules,
                "failed_capsules": self.progress.failed_capsules,
                "skipped_capsules": self.progress.skipped_capsules,
                "percent_complete": self.progress.percent_complete,
                "success_rate": self.progress.success_rate,
            },
            "error_message": self.error_message,
            "metadata": self.metadata,
        }


class EmbeddingMigrationService:
    """
    Service for migrating embeddings between versions.

    Features:
    - Background batch processing
    - Progress tracking and resumability
    - Automatic retries with backoff
    - Rollback support
    - Cleanup of old embeddings
    """

    def __init__(self) -> None:
        self._config = get_resilience_config().embedding_migration
        self._registry = get_version_registry()
        self._jobs: dict[str, MigrationJob] = {}
        self._active_job: str | None = None
        self._task: asyncio.Task[None] | None = None

        # Callbacks
        self._embed_callback: Callable[[str, str], Awaitable[list[float]]] | None = None
        self._store_callback: Callable[[str, list[float], str], Awaitable[bool]] | None = None
        self._cleanup_callback: Callable[[str, str], Awaitable[bool]] | None = None

        # Statistics
        self._stats = {
            "jobs_completed": 0,
            "jobs_failed": 0,
            "capsules_migrated": 0,
            "embeddings_cleaned": 0,
        }

    def set_embed_callback(self, callback: Callable[[str, str], Awaitable[list[float]]]) -> None:
        """
        Set callback for generating embeddings.

        Args:
            callback: Function(content, model_version) -> embedding_vector
        """
        self._embed_callback = callback

    def set_store_callback(
        self, callback: Callable[[str, list[float], str], Awaitable[bool]]
    ) -> None:
        """
        Set callback for storing embeddings.

        Args:
            callback: Function(capsule_id, embedding, version) -> success
        """
        self._store_callback = callback

    def set_cleanup_callback(self, callback: Callable[[str, str], Awaitable[bool]]) -> None:
        """
        Set callback for cleaning up old embeddings.

        Args:
            callback: Function(capsule_id, old_version) -> success
        """
        self._cleanup_callback = callback

    async def create_job(
        self,
        from_version: str,
        to_version: str,
        capsule_filter: dict[str, Any] | None = None,
        cleanup_old: bool | None = None,
    ) -> MigrationJob:
        """
        Create a new migration job.

        Args:
            from_version: Source embedding version
            to_version: Target embedding version
            capsule_filter: Optional filter for capsules to migrate
            cleanup_old: Whether to delete old embeddings after migration

        Returns:
            Created migration job
        """
        # Validate versions
        if not self._registry.get(from_version):
            raise ValueError(f"Unknown source version: {from_version}")
        if not self._registry.get(to_version):
            raise ValueError(f"Unknown target version: {to_version}")

        # Check migration path exists
        path = self._registry.get_migration_path(from_version, to_version)
        if not path:
            raise ValueError(f"No migration path from {from_version} to {to_version}")

        job = MigrationJob(
            job_id=f"mig_{secrets.token_urlsafe(8)}",
            from_version=from_version,
            to_version=to_version,
            capsule_filter=capsule_filter,
            batch_size=self._config.batch_size,
            delay_between_batches=self._config.delay_seconds,
            cleanup_old=cleanup_old
            if cleanup_old is not None
            else self._config.cleanup_old_embeddings,
        )

        self._jobs[job.job_id] = job

        logger.info(
            "migration_job_created",
            job_id=job.job_id,
            from_version=from_version,
            to_version=to_version,
        )

        return job

    async def start_job(self, job_id: str) -> bool:
        """
        Start a migration job.

        Args:
            job_id: ID of job to start

        Returns:
            True if job started successfully
        """
        if job_id not in self._jobs:
            return False

        if self._active_job:
            logger.warning("migration_job_already_active", active_job=self._active_job)
            return False

        job = self._jobs[job_id]
        if job.status not in (MigrationStatus.PENDING, MigrationStatus.PAUSED):
            return False

        self._active_job = job_id
        job.status = MigrationStatus.RUNNING
        job.started_at = datetime.now(UTC)

        # Start background task
        self._task = asyncio.create_task(self._run_migration(job))

        logger.info("migration_job_started", job_id=job_id)

        return True

    async def pause_job(self, job_id: str) -> bool:
        """Pause a running migration job."""
        if job_id not in self._jobs:
            return False

        job = self._jobs[job_id]
        if job.status != MigrationStatus.RUNNING:
            return False

        job.status = MigrationStatus.PAUSED
        logger.info("migration_job_paused", job_id=job_id)
        return True

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a migration job."""
        if job_id not in self._jobs:
            return False

        job = self._jobs[job_id]
        if job.status in (MigrationStatus.COMPLETED, MigrationStatus.CANCELLED):
            return False

        job.status = MigrationStatus.CANCELLED
        job.completed_at = datetime.now(UTC)

        if self._active_job == job_id:
            self._active_job = None
            if self._task:
                self._task.cancel()

        logger.info("migration_job_cancelled", job_id=job_id)
        return True

    async def rollback_job(self, job_id: str) -> bool:
        """
        Rollback a completed or failed migration.

        Args:
            job_id: Job to rollback

        Returns:
            True if rollback initiated
        """
        if job_id not in self._jobs:
            return False

        job = self._jobs[job_id]
        if job.status not in (MigrationStatus.COMPLETED, MigrationStatus.FAILED):
            return False

        if not job.cleanup_old:
            # If old embeddings weren't cleaned, just switch active version back
            self._registry.set_active(job.from_version)
            logger.info(
                "migration_rollback_version_switch", job_id=job_id, version=job.from_version
            )
            return True

        # Need to regenerate old embeddings
        job.status = MigrationStatus.ROLLING_BACK
        logger.info("migration_rollback_started", job_id=job_id)

        # Create reverse job
        rollback_job = await self.create_job(
            from_version=job.to_version,
            to_version=job.from_version,
            capsule_filter=job.capsule_filter,
            cleanup_old=True,
        )

        await self.start_job(rollback_job.job_id)
        return True

    def get_job(self, job_id: str) -> MigrationJob | None:
        """Get a migration job by ID."""
        return self._jobs.get(job_id)

    def list_jobs(self, status: MigrationStatus | None = None) -> list[MigrationJob]:
        """List all migration jobs, optionally filtered by status."""
        jobs = list(self._jobs.values())
        if status:
            jobs = [j for j in jobs if j.status == status]
        return jobs

    async def _run_migration(self, job: MigrationJob) -> None:
        """Run the migration job."""
        try:
            # Get capsules to migrate (placeholder - would query database)
            capsules = await self._get_capsules_to_migrate(job)
            job.progress.total_capsules = len(capsules)
            job.progress.total_batches = (len(capsules) + job.batch_size - 1) // job.batch_size

            logger.info(
                "migration_batch_processing_started",
                job_id=job.job_id,
                total_capsules=job.progress.total_capsules,
                total_batches=job.progress.total_batches,
            )

            # Process in batches
            for batch_num in range(0, len(capsules), job.batch_size):
                if job.status != MigrationStatus.RUNNING:
                    break

                job.progress.current_batch += 1
                batch = capsules[batch_num : batch_num + job.batch_size]

                await self._process_batch(job, batch)

                # Delay between batches
                if job.status == MigrationStatus.RUNNING:
                    await asyncio.sleep(job.delay_between_batches)

            if job.status == MigrationStatus.RUNNING:
                job.status = MigrationStatus.COMPLETED
                job.completed_at = datetime.now(UTC)
                self._stats["jobs_completed"] += 1
                self._stats["capsules_migrated"] += job.progress.processed_capsules

                # Switch active version
                self._registry.set_active(job.to_version)

                logger.info(
                    "migration_job_completed",
                    job_id=job.job_id,
                    processed=job.progress.processed_capsules,
                    failed=job.progress.failed_capsules,
                )

        except (RuntimeError, OSError, ValueError, ConnectionError) as e:
            job.status = MigrationStatus.FAILED
            job.error_message = str(e)
            job.completed_at = datetime.now(UTC)
            self._stats["jobs_failed"] += 1

            logger.error("migration_job_failed", job_id=job.job_id, error=str(e))

        finally:
            self._active_job = None

    async def _get_capsules_to_migrate(self, job: MigrationJob) -> list[dict[str, Any]]:
        """
        Get list of capsules that need migration.

        Queries the database for capsules based on:
        - Capsules with embeddings from the old version
        - Optional filters from the job (type, owner_id, tags)

        Args:
            job: Migration job with filter criteria

        Returns:
            List of capsule dicts with id and content for migration
        """
        try:
            db_client = await get_db_client()

            # Build filter conditions
            conditions = ["c.is_archived = false"]
            params: dict[str, Any] = {}

            # Filter by embedding version if capsules track it
            # Currently capsules may not have embedding_version field,
            # so we migrate all capsules with embeddings
            conditions.append("c.embedding IS NOT NULL")

            # Check for embedding_version field (optional - for future support)
            # If capsules have embedding_version, filter by from_version
            if job.from_version:
                # This will only match if the field exists and equals from_version
                # Otherwise we migrate all capsules with embeddings
                conditions.append(
                    "(c.embedding_version IS NULL OR c.embedding_version = $from_version)"
                )
                params["from_version"] = job.from_version

            # Apply optional filters from job
            # SECURITY FIX (Audit 4 - H17): Validate filter keys and values
            if job.capsule_filter:
                # Define allowed filter keys to prevent injection via unexpected keys
                ALLOWED_FILTER_KEYS = {"type", "owner_id", "tag", "min_trust"}

                # Check for unexpected filter keys
                unexpected_keys = set(job.capsule_filter.keys()) - ALLOWED_FILTER_KEYS
                if unexpected_keys:
                    logger.warning(
                        "unexpected_filter_keys_rejected",
                        job_id=job.job_id,
                        unexpected_keys=list(unexpected_keys),
                    )
                    # Don't fail, just ignore unexpected keys

                # Validate and apply type filter
                if job.capsule_filter.get("type"):
                    filter_type = job.capsule_filter["type"]
                    # Validate type is a simple string (no injection characters)
                    if isinstance(filter_type, str) and len(filter_type) <= 64:
                        conditions.append("c.type = $type")
                        params["type"] = filter_type

                # Validate and apply owner_id filter
                if job.capsule_filter.get("owner_id"):
                    owner_id = job.capsule_filter["owner_id"]
                    # Validate owner_id format (should be UUID-like)
                    if isinstance(owner_id, str) and len(owner_id) <= 64:
                        conditions.append("c.owner_id = $owner_id")
                        params["owner_id"] = owner_id

                # Validate and apply tag filter
                if job.capsule_filter.get("tag"):
                    tag = job.capsule_filter["tag"]
                    # Validate tag is a simple string
                    if isinstance(tag, str) and len(tag) <= 128:
                        conditions.append("$tag IN c.tags")
                        params["tag"] = tag

                # Validate and apply min_trust filter
                if job.capsule_filter.get("min_trust") is not None:
                    min_trust = job.capsule_filter["min_trust"]
                    # Validate min_trust is a number in valid range
                    if isinstance(min_trust, int | float) and 0 <= min_trust <= 100:
                        conditions.append("c.trust_level >= $min_trust")
                        params["min_trust"] = int(min_trust)

            where_clause = " AND ".join(conditions)

            query = f"""
            MATCH (c:Capsule)
            WHERE {where_clause}
            RETURN c.id AS id, c.content AS content, c.title AS title
            ORDER BY c.created_at ASC
            """

            results = await db_client.execute(query, params)

            capsules = [
                {
                    "id": r["id"],
                    "content": r["content"] or "",
                    "title": r.get("title", ""),
                }
                for r in results
                if r.get("id")
            ]

            logger.info(
                "capsules_to_migrate_fetched",
                job_id=job.job_id,
                count=len(capsules),
                filters=job.capsule_filter,
            )

            return capsules

        except (RuntimeError, OSError, ConnectionError, ValueError) as e:
            logger.error(
                "failed_to_fetch_capsules_for_migration",
                job_id=job.job_id,
                error=str(e),
            )
            raise

    async def _process_batch(self, job: MigrationJob, batch: list[dict[str, Any]]) -> None:
        """Process a batch of capsules."""
        for capsule in batch:
            if job.status != MigrationStatus.RUNNING:
                break

            try:
                success = await self._migrate_capsule(
                    capsule, job.from_version, job.to_version, job.cleanup_old
                )

                if success:
                    job.progress.processed_capsules += 1
                else:
                    job.progress.failed_capsules += 1

            except (RuntimeError, OSError, ConnectionError, ValueError, TypeError) as e:
                job.progress.failed_capsules += 1
                logger.warning(
                    "capsule_migration_error", capsule_id=capsule.get("id"), error=str(e)
                )

    async def _migrate_capsule(
        self, capsule: dict[str, Any], from_version: str, to_version: str, cleanup_old: bool
    ) -> bool:
        """Migrate a single capsule's embedding."""
        capsule_id: str = str(capsule.get("id", ""))
        content: str = str(capsule.get("content", ""))

        if not content:
            return True  # Nothing to embed

        # Generate new embedding
        if self._embed_callback:
            try:
                embedding = await self._embed_callback(content, to_version)
            except (RuntimeError, OSError, ConnectionError, ValueError, TypeError) as e:
                logger.error("embedding_generation_failed", capsule_id=capsule_id, error=str(e))
                return False
        else:
            # No callback set - simulate
            embedding = []

        # Store new embedding
        if self._store_callback:
            try:
                stored = await self._store_callback(capsule_id, embedding, to_version)
                if not stored:
                    return False
            except (RuntimeError, OSError, ConnectionError, ValueError, TypeError) as e:
                logger.error("embedding_store_failed", capsule_id=capsule_id, error=str(e))
                return False

        # Update the embedding version on the capsule
        try:
            if capsule_id is not None:
                await self._update_capsule_embedding_version(capsule_id, to_version)
        except (RuntimeError, OSError, ConnectionError, ValueError) as e:
            logger.warning("embedding_version_update_failed", capsule_id=capsule_id, error=str(e))

        # Cleanup old embedding
        if cleanup_old and self._cleanup_callback:
            try:
                await self._cleanup_callback(capsule_id, from_version)
                self._stats["embeddings_cleaned"] += 1
            except (RuntimeError, OSError, ConnectionError, ValueError) as e:
                logger.warning("old_embedding_cleanup_failed", capsule_id=capsule_id, error=str(e))

        return True

    async def _update_capsule_embedding_version(self, capsule_id: str, version: str) -> None:
        """
        Update the embedding version field on a capsule.

        Args:
            capsule_id: ID of the capsule to update
            version: New embedding version
        """
        try:
            db_client = await get_db_client()

            query = """
            MATCH (c:Capsule {id: $capsule_id})
            SET c.embedding_version = $version,
                c.updated_at = $now
            """

            from datetime import UTC, datetime

            await db_client.execute(
                query,
                {
                    "capsule_id": capsule_id,
                    "version": version,
                    "now": datetime.now(UTC).isoformat(),
                },
            )

        except (RuntimeError, OSError, ConnectionError, ValueError) as e:
            logger.warning(
                "failed_to_update_embedding_version",
                capsule_id=capsule_id,
                version=version,
                error=str(e),
            )

    def get_stats(self) -> dict[str, Any]:
        """Get migration statistics."""
        return dict(self._stats)


# Global service instance
_migration_service: EmbeddingMigrationService | None = None


async def get_migration_service() -> EmbeddingMigrationService:
    """Get or create the global migration service instance."""
    global _migration_service
    if _migration_service is None:
        _migration_service = EmbeddingMigrationService()
    return _migration_service
