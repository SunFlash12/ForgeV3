"""
Capsule Repository Tests for Forge Cascade V2

Comprehensive tests for CapsuleRepository including:
- Capsule CRUD operations
- Lineage and ancestry tracking
- Semantic search
- Integrity verification
- Semantic edges
"""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from forge.models.base import CapsuleType, TrustLevel
from forge.models.capsule import (
    Capsule,
    CapsuleCreate,
    CapsuleSearchResult,
    CapsuleUpdate,
    CapsuleWithLineage,
    IntegrityStatus,
    LineageNode,
)
from forge.models.semantic_edges import (
    SemanticEdge,
    SemanticEdgeCreate,
    SemanticNeighbor,
    SemanticRelationType,
)
from forge.repositories.capsule_repository import CapsuleRepository
from forge.security.capsule_integrity import CapsuleIntegrityService


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_db_client():
    """Create mock database client."""
    client = AsyncMock()
    client.execute = AsyncMock(return_value=[])
    client.execute_single = AsyncMock(return_value=None)
    return client


@pytest.fixture
def capsule_repository(mock_db_client):
    """Create capsule repository with mock client."""
    return CapsuleRepository(mock_db_client)


@pytest.fixture
def sample_capsule_data():
    """Sample capsule data for testing."""
    return {
        "id": "cap123",
        "content": "This is test capsule content.",
        "type": "INSIGHT",
        "title": "Test Capsule",
        "summary": "A test capsule for testing",
        "tags": ["test", "example"],
        "metadata": "{}",
        "version": "1.0.0",
        "owner_id": "user123",
        "trust_level": 60,
        "parent_id": None,
        "embedding": None,
        "is_archived": False,
        "view_count": 10,
        "fork_count": 2,
        "content_hash": "a" * 64,
        "merkle_root": "b" * 64,
        "parent_content_hash": None,
        "integrity_status": "valid",
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
    }


# =============================================================================
# Capsule Creation Tests
# =============================================================================


class TestCapsuleRepositoryCreate:
    """Tests for capsule creation."""

    @pytest.mark.asyncio
    async def test_create_capsule_success(
        self, capsule_repository, mock_db_client, sample_capsule_data
    ):
        """Successful capsule creation."""
        mock_db_client.execute_single.return_value = {"capsule": sample_capsule_data}

        capsule_create = CapsuleCreate(
            content="This is test capsule content.",
            type=CapsuleType.INSIGHT,
            title="Test Capsule",
            summary="A test capsule for testing",
            tags=["test", "example"],
        )

        result = await capsule_repository.create(
            data=capsule_create,
            owner_id="user123",
        )

        assert result.title == "Test Capsule"
        assert result.owner_id == "user123"
        mock_db_client.execute_single.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_capsule_with_embedding(
        self, capsule_repository, mock_db_client, sample_capsule_data
    ):
        """Capsule creation with embedding vector."""
        sample_capsule_data["embedding"] = [0.1, 0.2, 0.3]
        mock_db_client.execute_single.return_value = {"capsule": sample_capsule_data}

        capsule_create = CapsuleCreate(
            content="Content with embedding",
            type=CapsuleType.INSIGHT,
            title="Embedded Capsule",
        )

        result = await capsule_repository.create(
            data=capsule_create,
            owner_id="user123",
            embedding=[0.1, 0.2, 0.3],
        )

        call_args = mock_db_client.execute_single.call_args
        params = call_args[0][1]
        assert params["embedding"] == [0.1, 0.2, 0.3]

    @pytest.mark.asyncio
    async def test_create_capsule_with_parent(
        self, capsule_repository, mock_db_client, sample_capsule_data
    ):
        """Capsule creation with parent (fork)."""
        # First call returns parent data, second returns created capsule
        parent_data = {
            "content_hash": "parent_hash_123",
            "merkle_root": "parent_merkle_456",
            "content": "Parent content",
        }
        sample_capsule_data["parent_id"] = "parent123"
        sample_capsule_data["parent_content_hash"] = "parent_hash_123"

        mock_db_client.execute_single.side_effect = [parent_data, {"capsule": sample_capsule_data}]

        capsule_create = CapsuleCreate(
            content="Forked content",
            type=CapsuleType.INSIGHT,
            title="Forked Capsule",
            parent_id="parent123",
            evolution_reason="Adding improvements",
        )

        result = await capsule_repository.create(
            data=capsule_create,
            owner_id="user456",
        )

        assert result.parent_id == "parent123"

    @pytest.mark.asyncio
    async def test_create_capsule_computes_content_hash(
        self, capsule_repository, mock_db_client, sample_capsule_data
    ):
        """Capsule creation computes content hash."""
        mock_db_client.execute_single.return_value = {"capsule": sample_capsule_data}

        capsule_create = CapsuleCreate(
            content="Content to hash",
            type=CapsuleType.INSIGHT,
            title="Hashed Capsule",
        )

        await capsule_repository.create(
            data=capsule_create,
            owner_id="user123",
        )

        call_args = mock_db_client.execute_single.call_args
        params = call_args[0][1]

        # Verify content hash is computed (SHA-256 = 64 hex chars)
        assert len(params["content_hash"]) == 64
        assert len(params["merkle_root"]) == 64


# =============================================================================
# Capsule Update Tests
# =============================================================================


class TestCapsuleRepositoryUpdate:
    """Tests for capsule update operations."""

    @pytest.mark.asyncio
    async def test_update_capsule_content(
        self, capsule_repository, mock_db_client, sample_capsule_data
    ):
        """Update capsule content recomputes hash."""
        sample_capsule_data["content"] = "Updated content"
        mock_db_client.execute_single.return_value = {"capsule": sample_capsule_data}

        update = CapsuleUpdate(content="Updated content")
        result = await capsule_repository.update("cap123", update)

        assert result.content == "Updated content"
        call_args = mock_db_client.execute_single.call_args
        params = call_args[0][1]
        assert "content_hash" in params

    @pytest.mark.asyncio
    async def test_update_capsule_with_authorization(
        self, capsule_repository, mock_db_client, sample_capsule_data
    ):
        """Update capsule checks caller_id authorization."""
        mock_db_client.execute_single.return_value = {"capsule": sample_capsule_data}

        update = CapsuleUpdate(title="New Title")
        await capsule_repository.update("cap123", update, caller_id="user123")

        call_args = mock_db_client.execute_single.call_args
        params = call_args[0][1]
        assert params["caller_id"] == "user123"
        query = call_args[0][0]
        assert "owner_id = $caller_id" in query

    @pytest.mark.asyncio
    async def test_update_capsule_unauthorized_logs_warning(
        self, capsule_repository, mock_db_client, sample_capsule_data
    ):
        """Unauthorized update logs warning."""
        # First query returns None (unauthorized), second returns owner info
        mock_db_client.execute_single.side_effect = [
            None,  # Update failed
            {"owner_id": "other_user"},  # Owner check
        ]

        update = CapsuleUpdate(title="New Title")
        result = await capsule_repository.update("cap123", update, caller_id="user123")

        assert result is None


# =============================================================================
# Capsule Retrieval Tests
# =============================================================================


class TestCapsuleRepositoryRetrieval:
    """Tests for capsule retrieval operations."""

    @pytest.mark.asyncio
    async def test_get_by_owner(self, capsule_repository, mock_db_client, sample_capsule_data):
        """Get capsules by owner ID."""
        mock_db_client.execute.return_value = [{"capsule": sample_capsule_data}]

        result = await capsule_repository.get_by_owner("user123")

        assert len(result) == 1
        assert result[0].owner_id == "user123"

    @pytest.mark.asyncio
    async def test_get_by_owner_includes_archived(
        self, capsule_repository, mock_db_client, sample_capsule_data
    ):
        """Get capsules including archived."""
        sample_capsule_data["is_archived"] = True
        mock_db_client.execute.return_value = [{"capsule": sample_capsule_data}]

        result = await capsule_repository.get_by_owner("user123", include_archived=True)

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_recent(self, capsule_repository, mock_db_client, sample_capsule_data):
        """Get recent capsules."""
        mock_db_client.execute.return_value = [{"capsule": sample_capsule_data}]

        result = await capsule_repository.get_recent(limit=10)

        assert len(result) == 1
        call_args = mock_db_client.execute.call_args
        query = call_args[0][0]
        assert "ORDER BY c.created_at DESC" in query

    @pytest.mark.asyncio
    async def test_list_with_filters(self, capsule_repository, mock_db_client, sample_capsule_data):
        """List capsules with filters."""
        mock_db_client.execute_single.return_value = {"total": 1}
        mock_db_client.execute.return_value = [{"capsule": sample_capsule_data}]

        result, total = await capsule_repository.list(
            offset=0,
            limit=10,
            filters={"type": "insight", "tag": "test"},
        )

        assert len(result) == 1
        assert total == 1


# =============================================================================
# Lineage Tests
# =============================================================================


class TestCapsuleRepositoryLineage:
    """Tests for capsule lineage operations."""

    @pytest.mark.asyncio
    async def test_get_lineage(self, capsule_repository, mock_db_client, sample_capsule_data):
        """Get capsule with full lineage."""
        lineage_result = {
            "capsule": sample_capsule_data,
            "lineage": [
                {
                    "id": "ancestor1",
                    "version": "1.0.0",
                    "title": "Ancestor",
                    "type": "INSIGHT",
                    "created_at": datetime.now(UTC).isoformat(),
                    "trust_level": 60,
                    "depth": 1,
                }
            ],
            "children": [],
            "lineage_depth": 1,
        }
        mock_db_client.execute_single.return_value = lineage_result

        result = await capsule_repository.get_lineage("cap123")

        assert result is not None
        assert result.lineage_depth == 1
        assert len(result.lineage) == 1

    @pytest.mark.asyncio
    async def test_get_lineage_not_found(self, capsule_repository, mock_db_client):
        """Get lineage returns None for non-existent capsule."""
        mock_db_client.execute_single.return_value = None

        result = await capsule_repository.get_lineage("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_children(self, capsule_repository, mock_db_client, sample_capsule_data):
        """Get direct children (forks) of capsule."""
        child_data = {**sample_capsule_data, "id": "child1", "parent_id": "cap123"}
        mock_db_client.execute.return_value = [{"capsule": child_data}]

        result = await capsule_repository.get_children("cap123")

        assert len(result) == 1
        assert result[0].parent_id == "cap123"

    @pytest.mark.asyncio
    async def test_get_descendants_with_depth_limit(self, capsule_repository, mock_db_client):
        """Get descendants respects max depth."""
        mock_db_client.execute.return_value = [
            {
                "node": {
                    "id": "desc1",
                    "version": "1.0.0",
                    "title": "Desc",
                    "type": "INSIGHT",
                    "created_at": datetime.now(UTC).isoformat(),
                    "trust_level": 60,
                    "depth": 1,
                }
            }
        ]

        result = await capsule_repository.get_descendants("cap123", max_depth=5)

        assert len(result) == 1
        call_args = mock_db_client.execute.call_args
        query = call_args[0][0]
        assert "1..5" in query

    @pytest.mark.asyncio
    async def test_get_descendants_clamps_depth(self, capsule_repository, mock_db_client):
        """Get descendants clamps excessive depth."""
        mock_db_client.execute.return_value = []

        # Request depth > MAX_GRAPH_DEPTH
        await capsule_repository.get_descendants("cap123", max_depth=100)

        call_args = mock_db_client.execute.call_args
        query = call_args[0][0]
        # Should be clamped to MAX_GRAPH_DEPTH (20)
        assert "1..20" in query

    @pytest.mark.asyncio
    async def test_get_ancestors(self, capsule_repository, mock_db_client, sample_capsule_data):
        """Get ancestors of capsule."""
        mock_db_client.execute.return_value = [{"capsule": sample_capsule_data}]

        result = await capsule_repository.get_ancestors("cap123", max_depth=10)

        assert len(result) == 1


# =============================================================================
# Archive Tests
# =============================================================================


class TestCapsuleRepositoryArchive:
    """Tests for capsule archive operations."""

    @pytest.mark.asyncio
    async def test_archive_capsule(self, capsule_repository, mock_db_client, sample_capsule_data):
        """Archive capsule sets is_archived to True."""
        sample_capsule_data["is_archived"] = True
        mock_db_client.execute_single.return_value = {"entity": sample_capsule_data}

        result = await capsule_repository.archive("cap123")

        assert result.is_archived is True

    @pytest.mark.asyncio
    async def test_increment_view_count(self, capsule_repository, mock_db_client):
        """Increment view count."""
        await capsule_repository.increment_view_count("cap123")

        call_args = mock_db_client.execute.call_args
        query = call_args[0][0]
        assert "view_count + 1" in query


# =============================================================================
# Semantic Search Tests
# =============================================================================


class TestCapsuleRepositorySemanticSearch:
    """Tests for semantic search operations."""

    @pytest.mark.asyncio
    async def test_semantic_search_success(
        self, capsule_repository, mock_db_client, sample_capsule_data
    ):
        """Semantic search returns scored results."""
        mock_db_client.execute.return_value = [{"capsule": sample_capsule_data, "score": 0.95}]

        embedding = [0.1] * 1536
        result = await capsule_repository.semantic_search(
            query_embedding=embedding,
            limit=10,
        )

        assert len(result) == 1
        assert result[0].score == 0.95

    @pytest.mark.asyncio
    async def test_semantic_search_with_filters(
        self, capsule_repository, mock_db_client, sample_capsule_data
    ):
        """Semantic search with type and owner filters."""
        mock_db_client.execute.return_value = [{"capsule": sample_capsule_data, "score": 0.9}]

        embedding = [0.1] * 1536
        await capsule_repository.semantic_search(
            query_embedding=embedding,
            limit=10,
            min_trust=60,
            capsule_type=CapsuleType.INSIGHT,
            owner_id="user123",
        )

        call_args = mock_db_client.execute.call_args
        params = call_args[0][1]
        assert params["type"] == "insight"
        assert params["owner_id"] == "user123"

    @pytest.mark.asyncio
    async def test_semantic_search_handles_error(self, capsule_repository, mock_db_client):
        """Semantic search returns empty on error."""
        mock_db_client.execute.side_effect = Exception("Vector index not available")

        embedding = [0.1] * 1536
        result = await capsule_repository.semantic_search(
            query_embedding=embedding,
            limit=10,
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_find_similar_by_embedding(
        self, capsule_repository, mock_db_client, sample_capsule_data
    ):
        """Find similar capsules by embedding."""
        mock_db_client.execute.return_value = [{"capsule": sample_capsule_data, "score": 0.85}]

        embedding = [0.1] * 1536
        result = await capsule_repository.find_similar_by_embedding(
            embedding=embedding,
            limit=5,
            min_similarity=0.7,
            exclude_ids=["cap123"],
        )

        assert len(result) == 1
        assert result[0][1] == 0.85  # Score


# =============================================================================
# Integrity Verification Tests
# =============================================================================


class TestCapsuleRepositoryIntegrity:
    """Tests for capsule integrity verification."""

    @pytest.mark.asyncio
    async def test_verify_integrity_valid(self, capsule_repository, mock_db_client):
        """Verify valid capsule integrity."""
        content = "Test content for integrity"
        content_hash = CapsuleIntegrityService.compute_content_hash(content)

        mock_db_client.execute_single.return_value = {
            "content": content,
            "content_hash": content_hash,
            "merkle_root": "merkle123",
            "parent_content_hash": None,
            "signature": None,
            "integrity_status": "valid",
        }

        result = await capsule_repository.verify_integrity("cap123", update_status=False)

        assert result["valid"] is True
        assert result["found"] is True
        assert len(result["errors"]) == 0

    @pytest.mark.asyncio
    async def test_verify_integrity_corrupted(self, capsule_repository, mock_db_client):
        """Verify corrupted capsule integrity."""
        mock_db_client.execute_single.return_value = {
            "content": "Current content",
            "content_hash": "different_hash_that_wont_match",
            "merkle_root": "merkle123",
            "parent_content_hash": None,
            "signature": None,
            "integrity_status": "valid",
        }

        result = await capsule_repository.verify_integrity("cap123", update_status=False)

        assert result["valid"] is False
        assert "mismatch" in str(result["errors"])

    @pytest.mark.asyncio
    async def test_verify_integrity_not_found(self, capsule_repository, mock_db_client):
        """Verify non-existent capsule."""
        mock_db_client.execute_single.return_value = None

        result = await capsule_repository.verify_integrity("nonexistent")

        assert result["found"] is False
        assert result["valid"] is False

    @pytest.mark.asyncio
    async def test_verify_integrity_updates_status(self, capsule_repository, mock_db_client):
        """Verify integrity updates database status."""
        content = "Test content"
        content_hash = CapsuleIntegrityService.compute_content_hash(content)

        mock_db_client.execute_single.return_value = {
            "content": content,
            "content_hash": content_hash,
            "merkle_root": None,
            "parent_content_hash": None,
            "signature": None,
            "integrity_status": "valid",
        }
        mock_db_client.execute.return_value = []

        result = await capsule_repository.verify_integrity("cap123", update_status=True)

        assert result["status_updated"] is True
        # Verify update query was called
        assert mock_db_client.execute.called


# =============================================================================
# Semantic Edge Tests
# =============================================================================


class TestCapsuleRepositorySemanticEdges:
    """Tests for semantic edge operations."""

    @pytest.mark.asyncio
    async def test_create_semantic_edge(self, capsule_repository, mock_db_client):
        """Create semantic edge between capsules."""
        edge_data = {
            "id": "edge123",
            "source_id": "cap1",
            "target_id": "cap2",
            "relationship_type": "SUPPORTS",
            "confidence": 0.9,
            "reason": "Supporting evidence",
            "auto_detected": False,
            "properties": "{}",
            "bidirectional": False,
            "created_by": "user123",
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }

        # First call checks if edge exists, second creates it
        mock_db_client.execute_single.side_effect = [None, {"edge": edge_data}]

        edge_create = SemanticEdgeCreate(
            source_id="cap1",
            target_id="cap2",
            relationship_type=SemanticRelationType.SUPPORTS,
            confidence=0.9,
            reason="Supporting evidence",
        )

        result = await capsule_repository.create_semantic_edge(edge_create, "user123")

        assert result.source_id == "cap1"
        assert result.target_id == "cap2"
        assert result.relationship_type == SemanticRelationType.SUPPORTS

    @pytest.mark.asyncio
    async def test_create_semantic_edge_already_exists(self, capsule_repository, mock_db_client):
        """Create edge returns existing if already exists."""
        existing_edge = {
            "id": "edge123",
            "source_id": "cap1",
            "target_id": "cap2",
            "relationship_type": "SUPPORTS",
            "confidence": 0.8,
            "reason": "Existing",
            "auto_detected": False,
            "properties": "{}",
            "bidirectional": False,
            "created_by": "user123",
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }
        mock_db_client.execute_single.return_value = {"edge": existing_edge}

        edge_create = SemanticEdgeCreate(
            source_id="cap1",
            target_id="cap2",
            relationship_type=SemanticRelationType.SUPPORTS,
            confidence=0.9,
        )

        result = await capsule_repository.create_semantic_edge(edge_create, "user456")

        # Should return existing edge, not create new
        assert result.confidence == 0.8

    @pytest.mark.asyncio
    async def test_get_semantic_neighbors(self, capsule_repository, mock_db_client):
        """Get semantic neighbors of capsule."""
        mock_db_client.execute.return_value = [
            {
                "capsule_id": "cap2",
                "title": "Related Capsule",
                "capsule_type": "insight",
                "trust_level": 60,
                "relationship_type": "SUPPORTS",
                "confidence": 0.9,
                "edge_id": "edge123",
                "direction": "outgoing",
            }
        ]

        result = await capsule_repository.get_semantic_neighbors("cap1")

        assert len(result) == 1
        assert result[0].capsule_id == "cap2"
        assert result[0].relationship_type == SemanticRelationType.SUPPORTS

    @pytest.mark.asyncio
    async def test_get_semantic_neighbors_with_filters(self, capsule_repository, mock_db_client):
        """Get semantic neighbors with type filter."""
        mock_db_client.execute.return_value = []

        await capsule_repository.get_semantic_neighbors(
            "cap1",
            rel_types=[SemanticRelationType.SUPPORTS, SemanticRelationType.CONTRADICTS],
            direction="out",
            min_confidence=0.8,
        )

        call_args = mock_db_client.execute.call_args
        params = call_args[0][1]
        assert params["min_confidence"] == 0.8

    @pytest.mark.asyncio
    async def test_delete_semantic_edge(self, capsule_repository, mock_db_client):
        """Delete semantic edge."""
        mock_db_client.execute_single.return_value = {"deleted": 1}

        result = await capsule_repository.delete_semantic_edge("edge123")

        assert result is True

    @pytest.mark.asyncio
    async def test_update_semantic_edge(self, capsule_repository, mock_db_client):
        """Update semantic edge properties."""
        updated_edge = {
            "id": "edge123",
            "source_id": "cap1",
            "target_id": "cap2",
            "relationship_type": "SUPPORTS",
            "confidence": 0.95,
            "properties": '{"resolved": true}',
            "created_by": "user123",
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }
        mock_db_client.execute_single.return_value = {"edge": updated_edge}

        result = await capsule_repository.update_semantic_edge(
            "edge123",
            confidence=0.95,
            properties={"resolved": True},
        )

        assert result.confidence == 0.95


# =============================================================================
# Federation Sync Tests
# =============================================================================


class TestCapsuleRepositoryFederation:
    """Tests for federation sync operations."""

    @pytest.mark.asyncio
    async def test_get_changes_since(self, capsule_repository, mock_db_client, sample_capsule_data):
        """Get capsule changes since timestamp."""
        mock_db_client.execute.return_value = [{"capsule": sample_capsule_data}]

        since = datetime.now(UTC) - timedelta(hours=1)
        capsules, deleted_ids = await capsule_repository.get_changes_since(
            since=since,
            types=["insight"],
            min_trust=40,
        )

        assert len(capsules) == 1
        call_args = mock_db_client.execute.call_args
        params = call_args[0][1]
        assert "since" in params

    @pytest.mark.asyncio
    async def test_get_edges_since(self, capsule_repository, mock_db_client):
        """Get edge changes since timestamp."""
        mock_db_client.execute.return_value = [
            {
                "edge": {
                    "id": "e1->e2",
                    "source_id": "e1",
                    "target_id": "e2",
                    "relationship_type": "DERIVED_FROM",
                }
            }
        ]

        since = datetime.now(UTC) - timedelta(hours=1)
        edges = await capsule_repository.get_edges_since(since=since)

        assert len(edges) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
