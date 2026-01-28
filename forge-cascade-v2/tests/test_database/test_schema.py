"""
Neo4j Schema Manager Tests for Forge Cascade V2

Comprehensive tests for the SchemaManager including:
- Constraint creation (capsule, user, overlay, proposal, vote, auditlog, event)
- Index creation (standard and temporal indexes)
- Vector index creation
- Schema verification
- Schema drop operations
- Identifier validation security
- Error handling for various Neo4j exceptions
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from neo4j.exceptions import (
    ClientError,
    ConstraintError,
    DatabaseError,
    ServiceUnavailable,
)

from forge.database.schema import (
    SchemaManager,
    _SAFE_IDENTIFIER_PATTERN,
    _validate_identifier,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_db_client():
    """Create a mock database client."""
    client = AsyncMock()
    client.execute = AsyncMock(return_value=[])
    client.execute_single = AsyncMock(return_value=None)
    return client


@pytest.fixture
def schema_manager(mock_db_client):
    """Create a SchemaManager instance for testing."""
    return SchemaManager(mock_db_client)


# =============================================================================
# Identifier Validation Tests
# =============================================================================


class TestIdentifierValidation:
    """Tests for identifier validation security."""

    def test_validate_identifier_valid_simple(self):
        """Valid simple identifier passes."""
        assert _validate_identifier("constraint_name") is True

    def test_validate_identifier_valid_with_numbers(self):
        """Valid identifier with numbers passes."""
        assert _validate_identifier("constraint_123") is True

    def test_validate_identifier_valid_starts_with_underscore(self):
        """Valid identifier starting with underscore passes."""
        assert _validate_identifier("_constraint_name") is True

    def test_validate_identifier_valid_uppercase(self):
        """Valid uppercase identifier passes."""
        assert _validate_identifier("CONSTRAINT_NAME") is True

    def test_validate_identifier_valid_mixed_case(self):
        """Valid mixed case identifier passes."""
        assert _validate_identifier("Constraint_Name_123") is True

    def test_validate_identifier_invalid_starts_with_number(self):
        """Invalid identifier starting with number fails."""
        assert _validate_identifier("123_constraint") is False

    def test_validate_identifier_invalid_special_chars(self):
        """Invalid identifier with special characters fails."""
        assert _validate_identifier("constraint-name") is False
        assert _validate_identifier("constraint.name") is False
        assert _validate_identifier("constraint@name") is False
        assert _validate_identifier("constraint name") is False

    def test_validate_identifier_invalid_empty(self):
        """Empty identifier fails."""
        assert _validate_identifier("") is False

    def test_validate_identifier_invalid_too_long(self):
        """Identifier exceeding max length fails."""
        long_name = "a" * 129
        assert _validate_identifier(long_name) is False

    def test_validate_identifier_valid_max_length(self):
        """Identifier at max length passes."""
        max_name = "a" * 128
        assert _validate_identifier(max_name) is True

    def test_validate_identifier_invalid_injection_attempt(self):
        """SQL/Cypher injection attempts fail."""
        assert _validate_identifier("name; DROP CONSTRAINT") is False
        assert _validate_identifier("name' OR '1'='1") is False
        assert _validate_identifier("name`; MATCH (n) DELETE n") is False

    def test_safe_identifier_pattern(self):
        """Safe identifier pattern matches correctly."""
        assert _SAFE_IDENTIFIER_PATTERN.match("valid_name") is not None
        assert _SAFE_IDENTIFIER_PATTERN.match("ValidName123") is not None
        assert _SAFE_IDENTIFIER_PATTERN.match("_private") is not None
        assert _SAFE_IDENTIFIER_PATTERN.match("123invalid") is None
        assert _SAFE_IDENTIFIER_PATTERN.match("invalid-name") is None


# =============================================================================
# Constraint Creation Tests
# =============================================================================


class TestSchemaManagerConstraints:
    """Tests for constraint creation."""

    @pytest.mark.asyncio
    async def test_create_constraints_success(self, schema_manager, mock_db_client):
        """Create constraints successfully."""
        mock_db_client.execute.return_value = []

        results = await schema_manager.create_constraints()

        # Verify all expected constraints are created
        assert "capsule_id_unique" in results
        assert "user_id_unique" in results
        assert "user_username_unique" in results
        assert "user_email_unique" in results
        assert "overlay_id_unique" in results
        assert "overlay_name_unique" in results
        assert "proposal_id_unique" in results
        assert "vote_id_unique" in results
        assert "auditlog_id_unique" in results
        assert "event_id_unique" in results

        # All should succeed
        assert all(v is True for v in results.values())

    @pytest.mark.asyncio
    async def test_create_constraints_includes_graph_extensions(
        self, schema_manager, mock_db_client
    ):
        """Create constraints includes graph extension constraints."""
        mock_db_client.execute.return_value = []

        results = await schema_manager.create_constraints()

        # Graph extension constraints
        assert "capsuleversion_id_unique" in results
        assert "trustsnapshot_id_unique" in results
        assert "graphsnapshot_id_unique" in results
        assert "semanticedge_id_unique" in results

    @pytest.mark.asyncio
    async def test_create_constraints_includes_chat_room(
        self, schema_manager, mock_db_client
    ):
        """Create constraints includes chat room constraints."""
        mock_db_client.execute.return_value = []

        results = await schema_manager.create_constraints()

        # Chat room constraints
        assert "chatroom_id_unique" in results
        assert "chatroom_invite_code_unique" in results
        assert "chatmessage_id_unique" in results

    @pytest.mark.asyncio
    async def test_create_constraints_handles_constraint_error(
        self, schema_manager, mock_db_client
    ):
        """Create constraints handles ConstraintError gracefully."""
        call_count = [0]

        async def mock_execute(query, *args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise ConstraintError("Constraint already exists")
            return []

        mock_db_client.execute = mock_execute

        results = await schema_manager.create_constraints()

        # First constraint should fail, others succeed
        failed_count = sum(1 for v in results.values() if not v)
        assert failed_count == 1

    @pytest.mark.asyncio
    async def test_create_constraints_handles_client_error(
        self, schema_manager, mock_db_client
    ):
        """Create constraints handles ClientError gracefully."""
        call_count = [0]

        async def mock_execute(query, *args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 2:
                raise ClientError("Syntax error")
            return []

        mock_db_client.execute = mock_execute

        results = await schema_manager.create_constraints()

        # Second constraint should fail
        failed_count = sum(1 for v in results.values() if not v)
        assert failed_count == 1

    @pytest.mark.asyncio
    async def test_create_constraints_handles_database_error(
        self, schema_manager, mock_db_client
    ):
        """Create constraints handles DatabaseError gracefully."""
        call_count = [0]

        async def mock_execute(query, *args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 3:
                raise DatabaseError("Database error")
            return []

        mock_db_client.execute = mock_execute

        results = await schema_manager.create_constraints()

        failed_count = sum(1 for v in results.values() if not v)
        assert failed_count == 1

    @pytest.mark.asyncio
    async def test_create_constraints_raises_on_service_unavailable(
        self, schema_manager, mock_db_client
    ):
        """Create constraints raises on ServiceUnavailable."""
        mock_db_client.execute = AsyncMock(
            side_effect=ServiceUnavailable("Database unavailable")
        )

        with pytest.raises(ServiceUnavailable):
            await schema_manager.create_constraints()

    @pytest.mark.asyncio
    async def test_create_constraints_handles_unexpected_exception(
        self, schema_manager, mock_db_client
    ):
        """Create constraints handles unexpected exceptions gracefully."""
        call_count = [0]

        async def mock_execute(query, *args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise ValueError("Unexpected error")
            return []

        mock_db_client.execute = mock_execute

        results = await schema_manager.create_constraints()

        failed_count = sum(1 for v in results.values() if not v)
        assert failed_count == 1


# =============================================================================
# Index Creation Tests
# =============================================================================


class TestSchemaManagerIndexes:
    """Tests for index creation."""

    @pytest.mark.asyncio
    async def test_create_indexes_success(self, schema_manager, mock_db_client):
        """Create indexes successfully."""
        mock_db_client.execute.return_value = []

        results = await schema_manager.create_indexes()

        # Verify capsule indexes
        assert "capsule_type_idx" in results
        assert "capsule_owner_idx" in results
        assert "capsule_trust_idx" in results
        assert "capsule_created_idx" in results

        # Verify user indexes
        assert "user_role_idx" in results
        assert "user_active_idx" in results
        assert "user_trust_idx" in results

        # All should succeed
        assert all(v is True for v in results.values())

    @pytest.mark.asyncio
    async def test_create_indexes_includes_overlay_indexes(
        self, schema_manager, mock_db_client
    ):
        """Create indexes includes overlay indexes."""
        mock_db_client.execute.return_value = []

        results = await schema_manager.create_indexes()

        assert "overlay_state_idx" in results
        assert "overlay_trust_idx" in results

    @pytest.mark.asyncio
    async def test_create_indexes_includes_proposal_indexes(
        self, schema_manager, mock_db_client
    ):
        """Create indexes includes proposal indexes."""
        mock_db_client.execute.return_value = []

        results = await schema_manager.create_indexes()

        assert "proposal_status_idx" in results
        assert "proposal_proposer_idx" in results

    @pytest.mark.asyncio
    async def test_create_indexes_includes_audit_indexes(
        self, schema_manager, mock_db_client
    ):
        """Create indexes includes audit log indexes."""
        mock_db_client.execute.return_value = []

        results = await schema_manager.create_indexes()

        assert "audit_entity_idx" in results
        assert "audit_user_idx" in results
        assert "audit_timestamp_idx" in results
        assert "audit_correlation_idx" in results

    @pytest.mark.asyncio
    async def test_create_indexes_includes_event_indexes(
        self, schema_manager, mock_db_client
    ):
        """Create indexes includes event indexes."""
        mock_db_client.execute.return_value = []

        results = await schema_manager.create_indexes()

        assert "event_type_idx" in results
        assert "event_source_idx" in results
        assert "event_timestamp_idx" in results

    @pytest.mark.asyncio
    async def test_create_indexes_includes_temporal_indexes(
        self, schema_manager, mock_db_client
    ):
        """Create indexes includes temporal graph extension indexes."""
        mock_db_client.execute.return_value = []

        results = await schema_manager.create_indexes()

        # CapsuleVersion indexes
        assert "version_capsule_idx" in results
        assert "version_timestamp_idx" in results
        assert "version_type_idx" in results
        assert "version_creator_idx" in results

        # TrustSnapshot indexes
        assert "trustsnapshot_entity_idx" in results
        assert "trustsnapshot_time_idx" in results
        assert "trustsnapshot_type_idx" in results

        # GraphSnapshot indexes
        assert "graphsnapshot_time_idx" in results

    @pytest.mark.asyncio
    async def test_create_indexes_includes_semantic_edge_indexes(
        self, schema_manager, mock_db_client
    ):
        """Create indexes includes semantic edge indexes."""
        mock_db_client.execute.return_value = []

        results = await schema_manager.create_indexes()

        assert "semanticedge_source_idx" in results
        assert "semanticedge_target_idx" in results
        assert "semanticedge_type_idx" in results
        assert "semanticedge_confidence_idx" in results
        assert "semanticedge_created_idx" in results

    @pytest.mark.asyncio
    async def test_create_indexes_includes_chat_indexes(
        self, schema_manager, mock_db_client
    ):
        """Create indexes includes chat room indexes."""
        mock_db_client.execute.return_value = []

        results = await schema_manager.create_indexes()

        # ChatRoom indexes
        assert "chatroom_owner_idx" in results
        assert "chatroom_visibility_idx" in results
        assert "chatroom_created_idx" in results

        # RoomMember indexes
        assert "roommember_user_idx" in results
        assert "roommember_room_idx" in results
        assert "roommember_role_idx" in results

        # ChatMessage indexes
        assert "chatmessage_room_idx" in results
        assert "chatmessage_sender_idx" in results
        assert "chatmessage_created_idx" in results

    @pytest.mark.asyncio
    async def test_create_indexes_handles_client_error(
        self, schema_manager, mock_db_client
    ):
        """Create indexes handles ClientError gracefully."""
        call_count = [0]

        async def mock_execute(query, *args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise ClientError("Syntax error")
            return []

        mock_db_client.execute = mock_execute

        results = await schema_manager.create_indexes()

        failed_count = sum(1 for v in results.values() if not v)
        assert failed_count == 1

    @pytest.mark.asyncio
    async def test_create_indexes_handles_database_error(
        self, schema_manager, mock_db_client
    ):
        """Create indexes handles DatabaseError gracefully."""
        call_count = [0]

        async def mock_execute(query, *args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 2:
                raise DatabaseError("Index creation failed")
            return []

        mock_db_client.execute = mock_execute

        results = await schema_manager.create_indexes()

        failed_count = sum(1 for v in results.values() if not v)
        assert failed_count == 1

    @pytest.mark.asyncio
    async def test_create_indexes_raises_on_service_unavailable(
        self, schema_manager, mock_db_client
    ):
        """Create indexes raises on ServiceUnavailable."""
        mock_db_client.execute = AsyncMock(
            side_effect=ServiceUnavailable("Database unavailable")
        )

        with pytest.raises(ServiceUnavailable):
            await schema_manager.create_indexes()

    @pytest.mark.asyncio
    async def test_create_indexes_handles_unexpected_exception(
        self, schema_manager, mock_db_client
    ):
        """Create indexes handles unexpected exceptions gracefully."""
        call_count = [0]

        async def mock_execute(query, *args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise TypeError("Unexpected error")
            return []

        mock_db_client.execute = mock_execute

        results = await schema_manager.create_indexes()

        failed_count = sum(1 for v in results.values() if not v)
        assert failed_count == 1


# =============================================================================
# Vector Index Creation Tests
# =============================================================================


class TestSchemaManagerVectorIndexes:
    """Tests for vector index creation."""

    @pytest.mark.asyncio
    async def test_create_vector_indexes_success(self, schema_manager, mock_db_client):
        """Create vector indexes successfully."""
        mock_db_client.execute.return_value = []

        results = await schema_manager.create_vector_indexes()

        assert "capsule_embeddings" in results
        assert results["capsule_embeddings"] is True

    @pytest.mark.asyncio
    async def test_create_vector_indexes_handles_client_error(
        self, schema_manager, mock_db_client
    ):
        """Create vector indexes handles ClientError (unsupported)."""
        mock_db_client.execute = AsyncMock(
            side_effect=ClientError("Vector indexes not supported")
        )

        results = await schema_manager.create_vector_indexes()

        assert "capsule_embeddings" in results
        assert results["capsule_embeddings"] is False

    @pytest.mark.asyncio
    async def test_create_vector_indexes_handles_database_error(
        self, schema_manager, mock_db_client
    ):
        """Create vector indexes handles DatabaseError (version incompatibility)."""
        mock_db_client.execute = AsyncMock(
            side_effect=DatabaseError("Unsupported feature")
        )

        results = await schema_manager.create_vector_indexes()

        assert results["capsule_embeddings"] is False

    @pytest.mark.asyncio
    async def test_create_vector_indexes_raises_on_service_unavailable(
        self, schema_manager, mock_db_client
    ):
        """Create vector indexes raises on ServiceUnavailable."""
        mock_db_client.execute = AsyncMock(
            side_effect=ServiceUnavailable("Database unavailable")
        )

        with pytest.raises(ServiceUnavailable):
            await schema_manager.create_vector_indexes()

    @pytest.mark.asyncio
    async def test_create_vector_indexes_handles_unexpected_exception(
        self, schema_manager, mock_db_client
    ):
        """Create vector indexes handles unexpected exceptions gracefully."""
        mock_db_client.execute = AsyncMock(side_effect=RuntimeError("Unexpected error"))

        results = await schema_manager.create_vector_indexes()

        assert results["capsule_embeddings"] is False


# =============================================================================
# Setup All Tests
# =============================================================================


class TestSchemaManagerSetupAll:
    """Tests for setup_all method."""

    @pytest.mark.asyncio
    async def test_setup_all_success(self, schema_manager, mock_db_client):
        """Setup all schema elements successfully."""
        mock_db_client.execute.return_value = []

        results = await schema_manager.setup_all()

        # Should contain constraints, indexes, and vector indexes
        assert "capsule_id_unique" in results  # Constraint
        assert "capsule_type_idx" in results  # Index
        assert "capsule_embeddings" in results  # Vector index

        # Count totals
        total = len(results)
        successful = sum(1 for v in results.values() if v)
        assert successful == total

    @pytest.mark.asyncio
    async def test_setup_all_with_partial_failures(self, schema_manager, mock_db_client):
        """Setup all handles partial failures."""
        call_count = [0]

        async def mock_execute(query, *args, **kwargs):
            call_count[0] += 1
            # Fail some operations
            if call_count[0] in [1, 5, 10]:
                raise DatabaseError("Database error")
            return []

        mock_db_client.execute = mock_execute

        results = await schema_manager.setup_all()

        successful = sum(1 for v in results.values() if v)
        failed = sum(1 for v in results.values() if not v)

        assert failed == 3
        assert successful > 0


# =============================================================================
# Drop All Tests
# =============================================================================


class TestSchemaManagerDropAll:
    """Tests for drop_all method."""

    @pytest.mark.asyncio
    async def test_drop_all_blocked_in_production(self, schema_manager):
        """Drop all is blocked in production without force."""
        with patch("forge.database.schema.get_settings") as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.app_env = "production"
            mock_get_settings.return_value = mock_settings

            with pytest.raises(RuntimeError, match="blocked in production"):
                await schema_manager.drop_all()

    @pytest.mark.asyncio
    async def test_drop_all_allowed_in_production_with_force(
        self, schema_manager, mock_db_client
    ):
        """Drop all is allowed in production with force=True."""
        with patch("forge.database.schema.get_settings") as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.app_env = "production"
            mock_get_settings.return_value = mock_settings

            mock_db_client.execute.return_value = []

            # Should not raise
            results = await schema_manager.drop_all(force=True)

            assert isinstance(results, dict)

    @pytest.mark.asyncio
    async def test_drop_all_allowed_in_development(
        self, schema_manager, mock_db_client
    ):
        """Drop all is allowed in development environment."""
        with patch("forge.database.schema.get_settings") as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.app_env = "development"
            mock_get_settings.return_value = mock_settings

            mock_db_client.execute.return_value = []

            results = await schema_manager.drop_all()

            assert isinstance(results, dict)

    @pytest.mark.asyncio
    async def test_drop_all_allowed_in_testing(self, schema_manager, mock_db_client):
        """Drop all is allowed in testing environment."""
        with patch("forge.database.schema.get_settings") as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.app_env = "testing"
            mock_get_settings.return_value = mock_settings

            mock_db_client.execute.return_value = []

            results = await schema_manager.drop_all()

            assert isinstance(results, dict)

    @pytest.mark.asyncio
    async def test_drop_all_drops_constraints(self, schema_manager, mock_db_client):
        """Drop all drops existing constraints."""
        with patch("forge.database.schema.get_settings") as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.app_env = "testing"
            mock_get_settings.return_value = mock_settings

            # Return constraints on first call, empty on second
            mock_db_client.execute.side_effect = [
                [{"name": "test_constraint"}],  # SHOW CONSTRAINTS
                [],  # DROP CONSTRAINT
                [],  # SHOW INDEXES
            ]

            results = await schema_manager.drop_all()

            assert "drop_constraint_test_constraint" in results
            assert results["drop_constraint_test_constraint"] is True

    @pytest.mark.asyncio
    async def test_drop_all_drops_indexes(self, schema_manager, mock_db_client):
        """Drop all drops existing indexes."""
        with patch("forge.database.schema.get_settings") as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.app_env = "testing"
            mock_get_settings.return_value = mock_settings

            mock_db_client.execute.side_effect = [
                [],  # SHOW CONSTRAINTS
                [{"name": "test_index"}],  # SHOW INDEXES
                [],  # DROP INDEX
            ]

            results = await schema_manager.drop_all()

            assert "drop_index_test_index" in results
            assert results["drop_index_test_index"] is True

    @pytest.mark.asyncio
    async def test_drop_all_validates_identifiers(self, schema_manager, mock_db_client):
        """Drop all validates identifiers before dropping."""
        with patch("forge.database.schema.get_settings") as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.app_env = "testing"
            mock_get_settings.return_value = mock_settings

            # Malicious constraint name
            mock_db_client.execute.side_effect = [
                [{"name": "valid_constraint"}, {"name": "malicious; DROP DATABASE"}],
                [],  # DROP valid_constraint
                [],  # SHOW INDEXES
            ]

            results = await schema_manager.drop_all()

            # Valid constraint should be dropped
            assert "drop_constraint_valid_constraint" in results
            assert results["drop_constraint_valid_constraint"] is True

            # Invalid identifier should be skipped
            assert "drop_constraint_invalid" in results
            assert results["drop_constraint_invalid"] is False

    @pytest.mark.asyncio
    async def test_drop_all_handles_client_error(self, schema_manager, mock_db_client):
        """Drop all handles ClientError gracefully."""
        with patch("forge.database.schema.get_settings") as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.app_env = "testing"
            mock_get_settings.return_value = mock_settings

            call_count = [0]

            async def mock_execute(query, *args, **kwargs):
                call_count[0] += 1
                if call_count[0] == 1:
                    return [{"name": "test_constraint"}]
                if call_count[0] == 2:
                    raise ClientError("Drop failed")
                return []

            mock_db_client.execute = mock_execute

            results = await schema_manager.drop_all()

            assert results["drop_constraint_test_constraint"] is False

    @pytest.mark.asyncio
    async def test_drop_all_handles_database_error(self, schema_manager, mock_db_client):
        """Drop all handles DatabaseError gracefully."""
        with patch("forge.database.schema.get_settings") as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.app_env = "testing"
            mock_get_settings.return_value = mock_settings

            call_count = [0]

            async def mock_execute(query, *args, **kwargs):
                call_count[0] += 1
                if call_count[0] == 1:
                    return [{"name": "test_constraint"}]
                if call_count[0] == 2:
                    raise DatabaseError("Database error")
                return []

            mock_db_client.execute = mock_execute

            results = await schema_manager.drop_all()

            assert results["drop_constraint_test_constraint"] is False

    @pytest.mark.asyncio
    async def test_drop_all_raises_on_service_unavailable(
        self, schema_manager, mock_db_client
    ):
        """Drop all raises on ServiceUnavailable."""
        with patch("forge.database.schema.get_settings") as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.app_env = "testing"
            mock_get_settings.return_value = mock_settings

            mock_db_client.execute.side_effect = [
                [{"name": "test_constraint"}],
                ServiceUnavailable("Database unavailable"),
            ]

            with pytest.raises(ServiceUnavailable):
                await schema_manager.drop_all()

    @pytest.mark.asyncio
    async def test_drop_all_handles_unexpected_exception(
        self, schema_manager, mock_db_client
    ):
        """Drop all handles unexpected exceptions gracefully."""
        with patch("forge.database.schema.get_settings") as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.app_env = "testing"
            mock_get_settings.return_value = mock_settings

            call_count = [0]

            async def mock_execute(query, *args, **kwargs):
                call_count[0] += 1
                if call_count[0] == 1:
                    return [{"name": "test_constraint"}]
                if call_count[0] == 2:
                    raise KeyError("Unexpected error")
                return []

            mock_db_client.execute = mock_execute

            results = await schema_manager.drop_all()

            assert results["drop_constraint_test_constraint"] is False


# =============================================================================
# Verify Schema Tests
# =============================================================================


class TestSchemaManagerVerifySchema:
    """Tests for schema verification."""

    @pytest.mark.asyncio
    async def test_verify_schema_complete(self, schema_manager, mock_db_client):
        """Verify schema reports complete when all elements exist."""
        # Create complete constraint set
        expected_constraints = {
            "capsule_id_unique",
            "user_id_unique",
            "user_username_unique",
            "user_email_unique",
            "overlay_id_unique",
            "overlay_name_unique",
            "proposal_id_unique",
            "vote_id_unique",
            "auditlog_id_unique",
            "event_id_unique",
            "capsuleversion_id_unique",
            "trustsnapshot_id_unique",
            "graphsnapshot_id_unique",
            "semanticedge_id_unique",
            "chatroom_id_unique",
            "chatroom_invite_code_unique",
            "chatmessage_id_unique",
        }

        # Create complete index set
        expected_indexes = {
            "capsule_type_idx",
            "capsule_owner_idx",
            "capsule_trust_idx",
            "capsule_created_idx",
            "user_role_idx",
            "user_active_idx",
            "user_trust_idx",
            "overlay_state_idx",
            "overlay_trust_idx",
            "proposal_status_idx",
            "proposal_proposer_idx",
            "audit_entity_idx",
            "audit_user_idx",
            "audit_timestamp_idx",
            "audit_correlation_idx",
            "event_type_idx",
            "event_source_idx",
            "event_timestamp_idx",
            "version_capsule_idx",
            "version_timestamp_idx",
            "version_type_idx",
            "version_creator_idx",
            "trustsnapshot_entity_idx",
            "trustsnapshot_time_idx",
            "trustsnapshot_type_idx",
            "graphsnapshot_time_idx",
            "semanticedge_source_idx",
            "semanticedge_target_idx",
            "semanticedge_type_idx",
            "semanticedge_confidence_idx",
            "semanticedge_created_idx",
            "chatroom_owner_idx",
            "chatroom_visibility_idx",
            "chatroom_created_idx",
            "roommember_user_idx",
            "roommember_room_idx",
            "roommember_role_idx",
            "chatmessage_room_idx",
            "chatmessage_sender_idx",
            "chatmessage_created_idx",
        }

        mock_db_client.execute.side_effect = [
            # SHOW CONSTRAINTS
            [{"name": c} for c in expected_constraints],
            # SHOW INDEXES
            [{"name": i, "type": "RANGE"} for i in expected_indexes]
            + [{"name": "capsule_embeddings", "type": "VECTOR"}],
        ]

        result = await schema_manager.verify_schema()

        assert result["is_complete"] is True
        assert result["constraints"]["expected"] == len(expected_constraints)
        assert result["constraints"]["found"] == len(expected_constraints)
        assert len(result["constraints"]["missing"]) == 0
        assert len(result["indexes"]["missing"]) == 0

    @pytest.mark.asyncio
    async def test_verify_schema_missing_constraints(
        self, schema_manager, mock_db_client
    ):
        """Verify schema reports missing constraints."""
        mock_db_client.execute.side_effect = [
            # Missing some constraints
            [{"name": "capsule_id_unique"}, {"name": "user_id_unique"}],
            # Empty indexes
            [],
        ]

        result = await schema_manager.verify_schema()

        assert result["is_complete"] is False
        assert len(result["constraints"]["missing"]) > 0
        assert "user_email_unique" in result["constraints"]["missing"]

    @pytest.mark.asyncio
    async def test_verify_schema_missing_indexes(self, schema_manager, mock_db_client):
        """Verify schema reports missing indexes."""
        # All constraints present
        expected_constraints = {
            "capsule_id_unique",
            "user_id_unique",
            "user_username_unique",
            "user_email_unique",
            "overlay_id_unique",
            "overlay_name_unique",
            "proposal_id_unique",
            "vote_id_unique",
            "auditlog_id_unique",
            "event_id_unique",
            "capsuleversion_id_unique",
            "trustsnapshot_id_unique",
            "graphsnapshot_id_unique",
            "semanticedge_id_unique",
            "chatroom_id_unique",
            "chatroom_invite_code_unique",
            "chatmessage_id_unique",
        }

        mock_db_client.execute.side_effect = [
            [{"name": c} for c in expected_constraints],
            # Missing indexes
            [{"name": "capsule_type_idx", "type": "RANGE"}],
        ]

        result = await schema_manager.verify_schema()

        assert result["is_complete"] is False
        assert len(result["indexes"]["missing"]) > 0

    @pytest.mark.asyncio
    async def test_verify_schema_missing_vector_indexes(
        self, schema_manager, mock_db_client
    ):
        """Verify schema reports missing vector indexes."""
        mock_db_client.execute.side_effect = [
            [],  # No constraints
            [],  # No indexes
        ]

        result = await schema_manager.verify_schema()

        assert "capsule_embeddings" in result["vector_indexes"]["missing"]

    @pytest.mark.asyncio
    async def test_verify_schema_distinguishes_vector_indexes(
        self, schema_manager, mock_db_client
    ):
        """Verify schema distinguishes vector indexes from regular indexes."""
        mock_db_client.execute.side_effect = [
            [],  # Constraints
            [
                {"name": "capsule_type_idx", "type": "RANGE"},
                {"name": "capsule_embeddings", "type": "VECTOR"},
            ],
        ]

        result = await schema_manager.verify_schema()

        assert result["vector_indexes"]["found"] == 1
        assert result["indexes"]["found"] == 1

    @pytest.mark.asyncio
    async def test_verify_schema_empty_database(self, schema_manager, mock_db_client):
        """Verify schema handles empty database."""
        mock_db_client.execute.side_effect = [
            [],  # No constraints
            [],  # No indexes
        ]

        result = await schema_manager.verify_schema()

        assert result["is_complete"] is False
        assert result["constraints"]["found"] == 0
        assert result["indexes"]["found"] == 0
        assert len(result["constraints"]["missing"]) > 0
        assert len(result["indexes"]["missing"]) > 0


# =============================================================================
# SchemaManager Initialization Tests
# =============================================================================


class TestSchemaManagerInit:
    """Tests for SchemaManager initialization."""

    def test_init_with_client(self, mock_db_client):
        """SchemaManager initializes with client."""
        manager = SchemaManager(mock_db_client)
        assert manager.client is mock_db_client


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
