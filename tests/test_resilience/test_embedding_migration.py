"""
Tests for Embedding Migration Service
=====================================

Tests for forge/resilience/migration/embedding_migration.py
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from forge.resilience.migration.embedding_migration import (
    EmbeddingMigrationService,
    MigrationJob,
    MigrationProgress,
    MigrationStatus,
    get_migration_service,
)


class TestMigrationStatus:
    """Tests for MigrationStatus enum."""

    def test_status_values(self):
        """Test all status values."""
        assert MigrationStatus.PENDING.value == "pending"
        assert MigrationStatus.RUNNING.value == "running"
        assert MigrationStatus.PAUSED.value == "paused"
        assert MigrationStatus.COMPLETED.value == "completed"
        assert MigrationStatus.FAILED.value == "failed"
        assert MigrationStatus.CANCELLED.value == "cancelled"
        assert MigrationStatus.ROLLING_BACK.value == "rolling_back"


class TestMigrationProgress:
    """Tests for MigrationProgress dataclass."""

    def test_progress_defaults(self):
        """Test default progress values."""
        progress = MigrationProgress()

        assert progress.total_capsules == 0
        assert progress.processed_capsules == 0
        assert progress.failed_capsules == 0
        assert progress.skipped_capsules == 0
        assert progress.current_batch == 0
        assert progress.total_batches == 0

    def test_percent_complete_zero_total(self):
        """Test percent complete with zero total."""
        progress = MigrationProgress(total_capsules=0)

        assert progress.percent_complete == 0.0

    def test_percent_complete_calculation(self):
        """Test percent complete calculation."""
        progress = MigrationProgress(total_capsules=100, processed_capsules=50)

        assert progress.percent_complete == 50.0

    def test_success_rate_zero_processed(self):
        """Test success rate with nothing processed."""
        progress = MigrationProgress()

        assert progress.success_rate == 100.0

    def test_success_rate_calculation(self):
        """Test success rate calculation."""
        progress = MigrationProgress(processed_capsules=80, failed_capsules=20)

        assert progress.success_rate == 80.0


class TestMigrationJob:
    """Tests for MigrationJob dataclass."""

    def test_job_creation(self):
        """Test creating a migration job."""
        job = MigrationJob(
            job_id="mig_123",
            from_version="v1",
            to_version="v2",
        )

        assert job.job_id == "mig_123"
        assert job.from_version == "v1"
        assert job.to_version == "v2"
        assert job.status == MigrationStatus.PENDING
        assert job.started_at is None
        assert job.completed_at is None

    def test_job_to_dict(self):
        """Test converting job to dictionary."""
        job = MigrationJob(
            job_id="mig_456",
            from_version="v1",
            to_version="v2",
        )
        job.status = MigrationStatus.RUNNING
        job.progress.total_capsules = 100
        job.progress.processed_capsules = 50

        result = job.to_dict()

        assert result["job_id"] == "mig_456"
        assert result["from_version"] == "v1"
        assert result["to_version"] == "v2"
        assert result["status"] == "running"
        assert result["progress"]["total_capsules"] == 100
        assert result["progress"]["processed_capsules"] == 50
        assert result["progress"]["percent_complete"] == 50.0


class TestEmbeddingMigrationService:
    """Tests for EmbeddingMigrationService class."""

    @pytest.fixture
    def mock_config(self):
        """Create mock config."""
        config = MagicMock()
        config.batch_size = 10
        config.delay_seconds = 0.1
        config.cleanup_old_embeddings = True
        config.cleanup_grace_period_days = 30
        return config

    @pytest.fixture
    def mock_registry(self):
        """Create mock version registry."""
        registry = MagicMock()
        registry.get.return_value = MagicMock()
        registry.get_migration_path.return_value = ["v1", "v2"]
        registry.set_active.return_value = True
        return registry

    @pytest.fixture
    def service(self, mock_config, mock_registry):
        """Create a migration service instance."""
        with patch("forge.resilience.migration.embedding_migration.get_resilience_config") as mock:
            mock.return_value.embedding_migration = mock_config
            with patch(
                "forge.resilience.migration.embedding_migration.get_version_registry"
            ) as mock_reg:
                mock_reg.return_value = mock_registry
                return EmbeddingMigrationService()

    def test_service_creation(self, service):
        """Test service creation."""
        assert service._jobs == {}
        assert service._active_job is None

    def test_set_embed_callback(self, service):
        """Test setting embed callback."""
        callback = AsyncMock()

        service.set_embed_callback(callback)

        assert service._embed_callback == callback

    def test_set_store_callback(self, service):
        """Test setting store callback."""
        callback = AsyncMock()

        service.set_store_callback(callback)

        assert service._store_callback == callback

    def test_set_cleanup_callback(self, service):
        """Test setting cleanup callback."""
        callback = AsyncMock()

        service.set_cleanup_callback(callback)

        assert service._cleanup_callback == callback

    @pytest.mark.asyncio
    async def test_create_job(self, service, mock_registry):
        """Test creating a migration job."""
        job = await service.create_job("v1", "v2")

        assert job.from_version == "v1"
        assert job.to_version == "v2"
        assert job.status == MigrationStatus.PENDING
        assert job.job_id in service._jobs

    @pytest.mark.asyncio
    async def test_create_job_unknown_source(self, service, mock_registry):
        """Test creating job with unknown source version."""
        mock_registry.get.side_effect = [None, MagicMock()]

        with pytest.raises(ValueError, match="Unknown source version"):
            await service.create_job("unknown", "v2")

    @pytest.mark.asyncio
    async def test_create_job_unknown_target(self, service, mock_registry):
        """Test creating job with unknown target version."""
        mock_registry.get.side_effect = [MagicMock(), None]

        with pytest.raises(ValueError, match="Unknown target version"):
            await service.create_job("v1", "unknown")

    @pytest.mark.asyncio
    async def test_create_job_no_migration_path(self, service, mock_registry):
        """Test creating job with no migration path."""
        mock_registry.get_migration_path.return_value = None

        with pytest.raises(ValueError, match="No migration path"):
            await service.create_job("v1", "v3")

    @pytest.mark.asyncio
    async def test_start_job(self, service, mock_registry):
        """Test starting a migration job."""
        with patch(
            "forge.resilience.migration.embedding_migration.get_db_client"
        ) as mock_db:
            mock_client = AsyncMock()
            mock_client.execute.return_value = []
            mock_db.return_value = mock_client

            job = await service.create_job("v1", "v2")
            result = await service.start_job(job.job_id)

            assert result is True
            assert job.status == MigrationStatus.RUNNING
            assert service._active_job == job.job_id

    @pytest.mark.asyncio
    async def test_start_job_not_found(self, service):
        """Test starting nonexistent job."""
        result = await service.start_job("nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_start_job_already_active(self, service, mock_registry):
        """Test starting job when another is active."""
        with patch(
            "forge.resilience.migration.embedding_migration.get_db_client"
        ) as mock_db:
            mock_client = AsyncMock()
            mock_client.execute.return_value = []
            mock_db.return_value = mock_client

            job1 = await service.create_job("v1", "v2")
            await service.start_job(job1.job_id)

            job2 = await service.create_job("v2", "v3")
            result = await service.start_job(job2.job_id)

            assert result is False

    @pytest.mark.asyncio
    async def test_pause_job(self, service, mock_registry):
        """Test pausing a migration job."""
        with patch(
            "forge.resilience.migration.embedding_migration.get_db_client"
        ) as mock_db:
            mock_client = AsyncMock()
            mock_client.execute.return_value = []
            mock_db.return_value = mock_client

            job = await service.create_job("v1", "v2")
            await service.start_job(job.job_id)

            result = await service.pause_job(job.job_id)

            assert result is True
            assert job.status == MigrationStatus.PAUSED

    @pytest.mark.asyncio
    async def test_pause_job_not_running(self, service, mock_registry):
        """Test pausing job that's not running."""
        job = await service.create_job("v1", "v2")

        result = await service.pause_job(job.job_id)

        assert result is False

    @pytest.mark.asyncio
    async def test_cancel_job(self, service, mock_registry):
        """Test cancelling a migration job."""
        job = await service.create_job("v1", "v2")

        result = await service.cancel_job(job.job_id)

        assert result is True
        assert job.status == MigrationStatus.CANCELLED
        assert job.completed_at is not None

    @pytest.mark.asyncio
    async def test_cancel_job_already_completed(self, service, mock_registry):
        """Test cancelling already completed job."""
        job = await service.create_job("v1", "v2")
        job.status = MigrationStatus.COMPLETED

        result = await service.cancel_job(job.job_id)

        assert result is False

    @pytest.mark.asyncio
    async def test_rollback_job(self, service, mock_registry):
        """Test rolling back a completed job."""
        job = await service.create_job("v1", "v2", cleanup_old=False)
        job.status = MigrationStatus.COMPLETED

        result = await service.rollback_job(job.job_id)

        assert result is True
        mock_registry.set_active.assert_called_with("v1")

    @pytest.mark.asyncio
    async def test_rollback_job_not_completed(self, service, mock_registry):
        """Test rolling back job that's not completed."""
        job = await service.create_job("v1", "v2")

        result = await service.rollback_job(job.job_id)

        assert result is False

    def test_get_job(self, service, mock_registry):
        """Test getting a job by ID."""
        job = MigrationJob(job_id="test_job", from_version="v1", to_version="v2")
        service._jobs["test_job"] = job

        result = service.get_job("test_job")

        assert result == job

    def test_get_job_not_found(self, service):
        """Test getting nonexistent job."""
        result = service.get_job("nonexistent")

        assert result is None

    def test_list_jobs(self, service, mock_registry):
        """Test listing all jobs."""
        job1 = MigrationJob(job_id="job1", from_version="v1", to_version="v2")
        job2 = MigrationJob(
            job_id="job2",
            from_version="v2",
            to_version="v3",
            status=MigrationStatus.COMPLETED,
        )
        service._jobs["job1"] = job1
        service._jobs["job2"] = job2

        all_jobs = service.list_jobs()
        pending_jobs = service.list_jobs(status=MigrationStatus.PENDING)
        completed_jobs = service.list_jobs(status=MigrationStatus.COMPLETED)

        assert len(all_jobs) == 2
        assert len(pending_jobs) == 1
        assert len(completed_jobs) == 1

    def test_get_stats(self, service):
        """Test getting stats."""
        stats = service.get_stats()

        assert "jobs_completed" in stats
        assert "jobs_failed" in stats
        assert "capsules_migrated" in stats
        assert "embeddings_cleaned" in stats


class TestGlobalFunctions:
    """Tests for module-level functions."""

    @pytest.mark.asyncio
    async def test_get_migration_service(self):
        """Test getting global migration service."""
        with patch(
            "forge.resilience.migration.embedding_migration._migration_service", None
        ):
            with patch(
                "forge.resilience.migration.embedding_migration.get_resilience_config"
            ) as mock:
                mock_config = MagicMock()
                mock_config.embedding_migration.batch_size = 100
                mock.return_value = mock_config

                with patch(
                    "forge.resilience.migration.embedding_migration.get_version_registry"
                ) as mock_reg:
                    mock_reg.return_value = MagicMock()

                    service = await get_migration_service()

                    assert isinstance(service, EmbeddingMigrationService)
