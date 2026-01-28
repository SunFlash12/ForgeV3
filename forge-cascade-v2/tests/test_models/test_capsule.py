"""
Capsule Model Tests for Forge Cascade V2

Comprehensive tests for capsule models including:
- IntegrityStatus enum
- ContentBlock model
- CapsuleBase model (content, type, title, summary, tags, metadata validation)
- CapsuleCreate model (parent_id, evolution_reason)
- CapsuleUpdate model
- Capsule model (id, version, owner_id, trust_level, etc.)
- CapsuleInDB model (embedding, content_hash, integrity fields, merkle fields)
- LineageNode model
- DerivedFromRelation model
- CapsuleWithLineage model
- CapsuleSearchResult model
- CapsuleFork model
- CapsuleStats model
- IntegrityReport model
- LineageIntegrityReport model
"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from forge.models.base import CapsuleType, TrustLevel
from forge.models.capsule import (
    SHA256_PATTERN,
    Capsule,
    CapsuleBase,
    CapsuleCreate,
    CapsuleFork,
    CapsuleInDB,
    CapsuleSearchResult,
    CapsuleStats,
    CapsuleUpdate,
    CapsuleWithLineage,
    ContentBlock,
    DerivedFromRelation,
    IntegrityReport,
    IntegrityStatus,
    LineageIntegrityReport,
    LineageNode,
)

# =============================================================================
# IntegrityStatus Enum Tests
# =============================================================================


class TestIntegrityStatus:
    """Tests for IntegrityStatus enum."""

    def test_integrity_status_values(self):
        """IntegrityStatus has expected values."""
        assert IntegrityStatus.UNVERIFIED.value == "unverified"
        assert IntegrityStatus.VALID.value == "valid"
        assert IntegrityStatus.CORRUPTED.value == "corrupted"
        assert IntegrityStatus.PENDING.value == "pending"

    def test_integrity_status_is_string_enum(self):
        """IntegrityStatus can be used as string."""
        status = IntegrityStatus.VALID
        assert status.value == "valid"
        assert status == "valid"


# =============================================================================
# ContentBlock Tests
# =============================================================================


class TestContentBlock:
    """Tests for ContentBlock model."""

    def test_valid_content_block(self):
        """Valid content block data creates model."""
        block = ContentBlock(
            content="print('Hello, World!')",
            content_type="code",
            language="python",
            metadata={"line_numbers": True},
        )

        assert block.content == "print('Hello, World!')"
        assert block.content_type == "code"
        assert block.language == "python"
        assert block.metadata == {"line_numbers": True}

    def test_content_block_defaults(self):
        """ContentBlock has sensible defaults."""
        block = ContentBlock(content="Some text content")

        assert block.content == "Some text content"
        assert block.content_type == "text"
        assert block.language is None
        assert block.metadata == {}

    def test_content_block_requires_content(self):
        """ContentBlock requires content field."""
        with pytest.raises(ValidationError):
            ContentBlock()


# =============================================================================
# CapsuleBase Tests
# =============================================================================


class TestCapsuleBase:
    """Tests for CapsuleBase model."""

    def test_valid_capsule_base(self):
        """Valid capsule base data creates model."""
        capsule = CapsuleBase(
            content="This is knowledge content.",
            type=CapsuleType.KNOWLEDGE,
            title="Test Capsule",
            summary="A brief summary of the content.",
            tags=["test", "example"],
            metadata={"source": "unit_test"},
        )

        assert capsule.content == "This is knowledge content."
        assert capsule.type == CapsuleType.KNOWLEDGE
        assert capsule.title == "Test Capsule"
        assert capsule.summary == "A brief summary of the content."
        assert capsule.tags == ["test", "example"]
        assert capsule.metadata == {"source": "unit_test"}

    def test_content_required(self):
        """Content field is required."""
        with pytest.raises(ValidationError):
            CapsuleBase()

    def test_content_min_length(self):
        """Content must be at least 1 character."""
        with pytest.raises(ValidationError, match="String should have at least 1"):
            CapsuleBase(content="")

    def test_content_max_length(self):
        """Content must be at most 100000 characters."""
        with pytest.raises(ValidationError):
            CapsuleBase(content="a" * 100001)

    def test_content_at_max_length(self):
        """Content at exactly max length is valid."""
        capsule = CapsuleBase(content="a" * 100000)
        assert len(capsule.content) == 100000

    def test_title_max_length(self):
        """Title must be at most 500 characters."""
        with pytest.raises(ValidationError):
            CapsuleBase(content="test", title="a" * 501)

    def test_title_at_max_length(self):
        """Title at exactly max length is valid."""
        capsule = CapsuleBase(content="test", title="a" * 500)
        assert len(capsule.title) == 500

    def test_summary_max_length(self):
        """Summary must be at most 2000 characters."""
        with pytest.raises(ValidationError):
            CapsuleBase(content="test", summary="a" * 2001)

    def test_summary_at_max_length(self):
        """Summary at exactly max length is valid."""
        capsule = CapsuleBase(content="test", summary="a" * 2000)
        assert len(capsule.summary) == 2000

    def test_defaults(self):
        """CapsuleBase has sensible defaults."""
        capsule = CapsuleBase(content="Test content")

        assert capsule.type == CapsuleType.KNOWLEDGE
        assert capsule.title is None
        assert capsule.summary is None
        assert capsule.tags == []
        assert capsule.metadata == {}

    def test_all_capsule_types(self):
        """All CapsuleType values are accepted."""
        for capsule_type in CapsuleType:
            capsule = CapsuleBase(content="Test", type=capsule_type)
            assert capsule.type == capsule_type

    # Tags validation tests

    def test_tags_normalization_lowercase(self):
        """Tags are normalized to lowercase."""
        capsule = CapsuleBase(
            content="test",
            tags=["Python", "MACHINE_LEARNING", "DataScience"],
        )
        assert capsule.tags == ["python", "machine_learning", "datascience"]

    def test_tags_normalization_strip_whitespace(self):
        """Tags have whitespace stripped."""
        capsule = CapsuleBase(
            content="test",
            tags=["  python  ", " ai ", "  ml  "],
        )
        assert capsule.tags == ["python", "ai", "ml"]

    def test_tags_filter_empty(self):
        """Empty tags are filtered out."""
        capsule = CapsuleBase(
            content="test",
            tags=["python", "", "   ", "ai"],
        )
        assert capsule.tags == ["python", "ai"]

    def test_tags_max_count(self):
        """Tags are limited to 20 at field level."""
        # The validator truncates to 20, but pydantic field validation
        # with max_length=20 rejects lists > 20 before the validator runs
        with pytest.raises(ValidationError, match="at most 20"):
            CapsuleBase(
                content="test",
                tags=[f"tag{i}" for i in range(30)],
            )

    def test_tags_empty_list_allowed(self):
        """Empty tags list is allowed."""
        capsule = CapsuleBase(content="test", tags=[])
        assert capsule.tags == []

    # Metadata validation tests

    def test_metadata_valid_dict(self):
        """Valid metadata dict is accepted."""
        capsule = CapsuleBase(
            content="test",
            metadata={"key": "value", "number": 42, "nested": {"a": 1}},
        )
        assert capsule.metadata == {"key": "value", "number": 42, "nested": {"a": 1}}

    def test_metadata_empty_dict_allowed(self):
        """Empty metadata dict is allowed."""
        capsule = CapsuleBase(content="test", metadata={})
        assert capsule.metadata == {}

    def test_metadata_forbidden_keys_rejected(self):
        """Forbidden keys in metadata are rejected."""
        forbidden_keys = [
            "__proto__",
            "__prototype__",
            "__class__",
            "__bases__",
            "__mro__",
            "__subclasses__",
            "__init__",
            "constructor",
            "prototype",
        ]

        for key in forbidden_keys:
            with pytest.raises(ValidationError, match="Forbidden keys"):
                CapsuleBase(content="test", metadata={key: "value"})

    def test_metadata_nested_forbidden_keys_rejected(self):
        """Forbidden keys in nested metadata are rejected."""
        with pytest.raises(ValidationError, match="Forbidden keys"):
            CapsuleBase(
                content="test",
                metadata={"safe": {"__proto__": "evil"}},
            )

    def test_metadata_max_depth(self):
        """Deeply nested metadata is rejected."""
        # Create dict with depth > 5
        deep_dict: dict = {"level": 1}
        current = deep_dict
        for i in range(2, 8):
            current["nested"] = {"level": i}
            current = current["nested"]

        with pytest.raises(ValidationError, match="nesting too deep"):
            CapsuleBase(content="test", metadata=deep_dict)

    def test_metadata_max_keys(self):
        """Metadata with too many keys is rejected."""
        too_many_keys = {f"key{i}": i for i in range(150)}
        with pytest.raises(ValidationError, match="Too many keys"):
            CapsuleBase(content="test", metadata=too_many_keys)


# =============================================================================
# CapsuleCreate Tests
# =============================================================================


class TestCapsuleCreate:
    """Tests for CapsuleCreate model."""

    def test_valid_capsule_create(self):
        """Valid capsule create data."""
        capsule = CapsuleCreate(
            content="New knowledge content",
            type=CapsuleType.INSIGHT,
            parent_id="parent123",
            evolution_reason="Extending parent knowledge",
        )

        assert capsule.content == "New knowledge content"
        assert capsule.parent_id == "parent123"
        assert capsule.evolution_reason == "Extending parent knowledge"

    def test_capsule_create_defaults(self):
        """CapsuleCreate has sensible defaults."""
        capsule = CapsuleCreate(content="Test content")

        assert capsule.parent_id is None
        assert capsule.evolution_reason is None

    def test_evolution_reason_max_length(self):
        """Evolution reason must be at most 1000 characters."""
        with pytest.raises(ValidationError):
            CapsuleCreate(
                content="test",
                evolution_reason="a" * 1001,
            )

    def test_evolution_reason_at_max_length(self):
        """Evolution reason at exactly max length is valid."""
        capsule = CapsuleCreate(
            content="test",
            evolution_reason="a" * 1000,
        )
        assert len(capsule.evolution_reason) == 1000

    def test_inherits_from_capsule_base(self):
        """CapsuleCreate inherits CapsuleBase validation."""
        # Tags normalization
        capsule = CapsuleCreate(
            content="test",
            tags=["TAG1", "  TAG2  "],
        )
        assert capsule.tags == ["tag1", "tag2"]


# =============================================================================
# CapsuleUpdate Tests
# =============================================================================


class TestCapsuleUpdate:
    """Tests for CapsuleUpdate model."""

    def test_capsule_update_all_optional(self):
        """CapsuleUpdate has all optional fields."""
        update = CapsuleUpdate()
        assert update.content is None
        assert update.title is None
        assert update.summary is None
        assert update.tags is None
        assert update.metadata is None

    def test_capsule_update_partial(self):
        """CapsuleUpdate allows partial updates."""
        update = CapsuleUpdate(title="New Title")
        assert update.title == "New Title"
        assert update.content is None

    def test_content_min_length_when_provided(self):
        """Content must be at least 1 character when provided."""
        with pytest.raises(ValidationError, match="String should have at least 1"):
            CapsuleUpdate(content="")

    def test_content_max_length(self):
        """Content must be at most 100000 characters."""
        with pytest.raises(ValidationError):
            CapsuleUpdate(content="a" * 100001)

    def test_title_max_length(self):
        """Title must be at most 500 characters."""
        with pytest.raises(ValidationError):
            CapsuleUpdate(title="a" * 501)

    def test_summary_max_length(self):
        """Summary must be at most 2000 characters."""
        with pytest.raises(ValidationError):
            CapsuleUpdate(summary="a" * 2001)


# =============================================================================
# Capsule Tests
# =============================================================================


class TestCapsule:
    """Tests for Capsule model."""

    def test_valid_capsule(self):
        """Valid capsule data creates model."""
        now = datetime.now(UTC)
        capsule = Capsule(
            id="cap123",
            content="Knowledge content",
            owner_id="user456",
            created_at=now,
            updated_at=now,
        )

        assert capsule.id == "cap123"
        assert capsule.content == "Knowledge content"
        assert capsule.owner_id == "user456"

    def test_capsule_defaults(self):
        """Capsule has sensible defaults."""
        now = datetime.now(UTC)
        capsule = Capsule(
            id="cap123",
            content="Test content",
            owner_id="user456",
            created_at=now,
            updated_at=now,
        )

        assert capsule.version == "1.0.0"
        assert capsule.trust_level == TrustLevel.STANDARD
        assert capsule.parent_id is None
        assert capsule.is_archived is False
        assert capsule.view_count == 0
        assert capsule.fork_count == 0

    def test_view_count_non_negative(self):
        """View count must be non-negative."""
        now = datetime.now(UTC)
        with pytest.raises(ValidationError):
            Capsule(
                id="cap123",
                content="Test",
                owner_id="user456",
                view_count=-1,
                created_at=now,
                updated_at=now,
            )

    def test_fork_count_non_negative(self):
        """Fork count must be non-negative."""
        now = datetime.now(UTC)
        with pytest.raises(ValidationError):
            Capsule(
                id="cap123",
                content="Test",
                owner_id="user456",
                fork_count=-1,
                created_at=now,
                updated_at=now,
            )

    def test_all_trust_levels(self):
        """All TrustLevel values are accepted."""
        now = datetime.now(UTC)
        for trust_level in TrustLevel:
            capsule = Capsule(
                id="cap123",
                content="Test",
                owner_id="user456",
                trust_level=trust_level,
                created_at=now,
                updated_at=now,
            )
            assert capsule.trust_level == trust_level

    def test_capsule_inherits_timestamp_mixin(self):
        """Capsule has timestamp fields."""
        now = datetime.now(UTC)
        capsule = Capsule(
            id="cap123",
            content="Test",
            owner_id="user456",
            created_at=now,
            updated_at=now,
        )
        assert capsule.created_at is not None
        assert capsule.updated_at is not None


# =============================================================================
# CapsuleInDB Tests
# =============================================================================


class TestCapsuleInDB:
    """Tests for CapsuleInDB model."""

    def test_valid_capsule_in_db(self):
        """Valid CapsuleInDB data creates model."""
        now = datetime.now(UTC)
        valid_hash = "a" * 64  # Valid SHA-256 (64 hex chars)

        capsule = CapsuleInDB(
            id="cap123",
            content="Test content",
            owner_id="user456",
            content_hash=valid_hash,
            integrity_status=IntegrityStatus.VALID,
            integrity_verified_at=now,
            created_at=now,
            updated_at=now,
        )

        assert capsule.content_hash == valid_hash
        assert capsule.integrity_status == IntegrityStatus.VALID

    def test_capsule_in_db_defaults(self):
        """CapsuleInDB has sensible defaults."""
        now = datetime.now(UTC)
        capsule = CapsuleInDB(
            id="cap123",
            content="Test",
            owner_id="user456",
            created_at=now,
            updated_at=now,
        )

        assert capsule.embedding is None
        assert capsule.content_hash is None
        assert capsule.integrity_status == IntegrityStatus.UNVERIFIED
        assert capsule.integrity_verified_at is None
        assert capsule.signature is None
        assert capsule.signature_algorithm == "Ed25519"
        assert capsule.signed_at is None
        assert capsule.signed_by is None
        assert capsule.parent_content_hash is None
        assert capsule.merkle_root is None

    # SHA-256 hash validation tests

    def test_content_hash_valid_sha256(self):
        """Valid SHA-256 hash is accepted."""
        now = datetime.now(UTC)
        valid_hash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

        capsule = CapsuleInDB(
            id="cap123",
            content="Test",
            owner_id="user456",
            content_hash=valid_hash,
            created_at=now,
            updated_at=now,
        )
        assert capsule.content_hash == valid_hash

    def test_content_hash_invalid_length(self):
        """Invalid hash length is rejected."""
        now = datetime.now(UTC)
        with pytest.raises(ValidationError, match="valid SHA-256"):
            CapsuleInDB(
                id="cap123",
                content="Test",
                owner_id="user456",
                content_hash="abc123",  # Too short
                created_at=now,
                updated_at=now,
            )

    def test_content_hash_invalid_characters(self):
        """Non-hex characters in hash are rejected."""
        now = datetime.now(UTC)
        with pytest.raises(ValidationError, match="valid SHA-256"):
            CapsuleInDB(
                id="cap123",
                content="Test",
                owner_id="user456",
                content_hash="g" * 64,  # 'g' is not hex
                created_at=now,
                updated_at=now,
            )

    def test_content_hash_uppercase_rejected(self):
        """Uppercase hex characters are rejected (must be lowercase)."""
        now = datetime.now(UTC)
        with pytest.raises(ValidationError, match="valid SHA-256"):
            CapsuleInDB(
                id="cap123",
                content="Test",
                owner_id="user456",
                content_hash="A" * 64,  # Uppercase
                created_at=now,
                updated_at=now,
            )

    def test_content_hash_none_allowed(self):
        """None content_hash is allowed."""
        now = datetime.now(UTC)
        capsule = CapsuleInDB(
            id="cap123",
            content="Test",
            owner_id="user456",
            content_hash=None,
            created_at=now,
            updated_at=now,
        )
        assert capsule.content_hash is None

    # Merkle root validation tests

    def test_merkle_root_valid(self):
        """Valid merkle root is accepted."""
        now = datetime.now(UTC)
        valid_hash = "a" * 64

        capsule = CapsuleInDB(
            id="cap123",
            content="Test",
            owner_id="user456",
            merkle_root=valid_hash,
            created_at=now,
            updated_at=now,
        )
        assert capsule.merkle_root == valid_hash

    def test_merkle_root_invalid(self):
        """Invalid merkle root is rejected."""
        now = datetime.now(UTC)
        with pytest.raises(ValidationError, match="valid SHA-256"):
            CapsuleInDB(
                id="cap123",
                content="Test",
                owner_id="user456",
                merkle_root="invalid",
                created_at=now,
                updated_at=now,
            )

    # Parent content hash validation tests

    def test_parent_content_hash_valid(self):
        """Valid parent content hash is accepted."""
        now = datetime.now(UTC)
        valid_hash = "b" * 64

        capsule = CapsuleInDB(
            id="cap123",
            content="Test",
            owner_id="user456",
            parent_content_hash=valid_hash,
            created_at=now,
            updated_at=now,
        )
        assert capsule.parent_content_hash == valid_hash

    def test_parent_content_hash_invalid(self):
        """Invalid parent content hash is rejected."""
        now = datetime.now(UTC)
        with pytest.raises(ValidationError, match="valid SHA-256"):
            CapsuleInDB(
                id="cap123",
                content="Test",
                owner_id="user456",
                parent_content_hash="not_a_hash",
                created_at=now,
                updated_at=now,
            )

    # Embedding validation tests

    def test_embedding_valid_1536_dimensions(self):
        """Valid 1536-dimensional embedding (OpenAI) is accepted."""
        now = datetime.now(UTC)
        embedding = [0.1] * 1536

        capsule = CapsuleInDB(
            id="cap123",
            content="Test",
            owner_id="user456",
            embedding=embedding,
            created_at=now,
            updated_at=now,
        )
        assert len(capsule.embedding) == 1536

    def test_embedding_valid_384_dimensions(self):
        """Valid 384-dimensional embedding is accepted."""
        now = datetime.now(UTC)
        capsule = CapsuleInDB(
            id="cap123",
            content="Test",
            owner_id="user456",
            embedding=[0.5] * 384,
            created_at=now,
            updated_at=now,
        )
        assert len(capsule.embedding) == 384

    def test_embedding_valid_768_dimensions(self):
        """Valid 768-dimensional embedding is accepted."""
        now = datetime.now(UTC)
        capsule = CapsuleInDB(
            id="cap123",
            content="Test",
            owner_id="user456",
            embedding=[0.5] * 768,
            created_at=now,
            updated_at=now,
        )
        assert len(capsule.embedding) == 768

    def test_embedding_valid_1024_dimensions(self):
        """Valid 1024-dimensional embedding is accepted."""
        now = datetime.now(UTC)
        capsule = CapsuleInDB(
            id="cap123",
            content="Test",
            owner_id="user456",
            embedding=[0.5] * 1024,
            created_at=now,
            updated_at=now,
        )
        assert len(capsule.embedding) == 1024

    def test_embedding_valid_3072_dimensions(self):
        """Valid 3072-dimensional embedding is accepted."""
        now = datetime.now(UTC)
        capsule = CapsuleInDB(
            id="cap123",
            content="Test",
            owner_id="user456",
            embedding=[0.5] * 3072,
            created_at=now,
            updated_at=now,
        )
        assert len(capsule.embedding) == 3072

    def test_embedding_invalid_dimensions(self):
        """Invalid embedding dimensions are rejected."""
        now = datetime.now(UTC)
        with pytest.raises(ValidationError, match="valid dimensions"):
            CapsuleInDB(
                id="cap123",
                content="Test",
                owner_id="user456",
                embedding=[0.1] * 100,  # Invalid dimension
                created_at=now,
                updated_at=now,
            )

    def test_embedding_value_range_valid(self):
        """Embedding values within valid range are accepted."""
        now = datetime.now(UTC)
        # Values between -10 and 10
        embedding = [-5.0, 0.0, 5.0, -1.0, 1.0] * (1536 // 5) + [-5.0]

        capsule = CapsuleInDB(
            id="cap123",
            content="Test",
            owner_id="user456",
            embedding=embedding,
            created_at=now,
            updated_at=now,
        )
        assert capsule.embedding is not None

    def test_embedding_value_too_high(self):
        """Embedding value > 10 is rejected."""
        now = datetime.now(UTC)
        embedding = [0.0] * 1535 + [15.0]  # Last value too high

        with pytest.raises(ValidationError, match="out of valid range"):
            CapsuleInDB(
                id="cap123",
                content="Test",
                owner_id="user456",
                embedding=embedding,
                created_at=now,
                updated_at=now,
            )

    def test_embedding_value_too_low(self):
        """Embedding value < -10 is rejected."""
        now = datetime.now(UTC)
        embedding = [-15.0] + [0.0] * 1535  # First value too low

        with pytest.raises(ValidationError, match="out of valid range"):
            CapsuleInDB(
                id="cap123",
                content="Test",
                owner_id="user456",
                embedding=embedding,
                created_at=now,
                updated_at=now,
            )

    def test_embedding_none_allowed(self):
        """None embedding is allowed."""
        now = datetime.now(UTC)
        capsule = CapsuleInDB(
            id="cap123",
            content="Test",
            owner_id="user456",
            embedding=None,
            created_at=now,
            updated_at=now,
        )
        assert capsule.embedding is None

    def test_embedding_boundary_values(self):
        """Embedding values at boundaries (-10, 10) are accepted."""
        now = datetime.now(UTC)
        embedding = [-10.0, 10.0] * (1536 // 2)

        capsule = CapsuleInDB(
            id="cap123",
            content="Test",
            owner_id="user456",
            embedding=embedding,
            created_at=now,
            updated_at=now,
        )
        assert capsule.embedding is not None

    def test_signature_fields(self):
        """Signature fields are properly stored."""
        now = datetime.now(UTC)
        capsule = CapsuleInDB(
            id="cap123",
            content="Test",
            owner_id="user456",
            signature="base64encodedSignature==",
            signature_algorithm="Ed25519",
            signed_at=now,
            signed_by="signer789",
            created_at=now,
            updated_at=now,
        )

        assert capsule.signature == "base64encodedSignature=="
        assert capsule.signature_algorithm == "Ed25519"
        assert capsule.signed_by == "signer789"


# =============================================================================
# LineageNode Tests
# =============================================================================


class TestLineageNode:
    """Tests for LineageNode model."""

    def test_valid_lineage_node(self):
        """Valid lineage node data creates model."""
        now = datetime.now(UTC)
        node = LineageNode(
            id="node123",
            version="1.0.0",
            title="Test Node",
            type=CapsuleType.KNOWLEDGE,
            created_at=now,
            trust_level=TrustLevel.STANDARD,
            depth=0,
        )

        assert node.id == "node123"
        assert node.version == "1.0.0"
        assert node.depth == 0

    def test_lineage_node_depth_non_negative(self):
        """Depth must be non-negative."""
        now = datetime.now(UTC)
        with pytest.raises(ValidationError):
            LineageNode(
                id="node123",
                version="1.0.0",
                type=CapsuleType.KNOWLEDGE,
                created_at=now,
                trust_level=TrustLevel.STANDARD,
                depth=-1,
            )

    def test_lineage_node_optional_title(self):
        """LineageNode has optional title field."""
        now = datetime.now(UTC)
        node = LineageNode(
            id="node123",
            version="1.0.0",
            type=CapsuleType.KNOWLEDGE,
            created_at=now,
            trust_level=TrustLevel.STANDARD,
            depth=0,  # depth is required
        )

        assert node.title is None


# =============================================================================
# DerivedFromRelation Tests
# =============================================================================


class TestDerivedFromRelation:
    """Tests for DerivedFromRelation model."""

    def test_valid_derived_from_relation(self):
        """Valid derived from relation data creates model."""
        now = datetime.now(UTC)
        relation = DerivedFromRelation(
            parent_id="parent123",
            child_id="child456",
            reason="Extended with additional context",
            timestamp=now,
            changes={"added_fields": ["summary"]},
        )

        assert relation.parent_id == "parent123"
        assert relation.child_id == "child456"
        assert relation.reason == "Extended with additional context"

    def test_derived_from_relation_defaults(self):
        """DerivedFromRelation has sensible defaults."""
        now = datetime.now(UTC)
        relation = DerivedFromRelation(
            parent_id="parent123",
            child_id="child456",
            timestamp=now,
        )

        assert relation.reason is None
        assert relation.changes is None

    def test_derived_from_relation_required_fields(self):
        """DerivedFromRelation requires essential fields."""
        with pytest.raises(ValidationError):
            DerivedFromRelation(parent_id="parent123")  # Missing child_id and timestamp


# =============================================================================
# CapsuleWithLineage Tests
# =============================================================================


class TestCapsuleWithLineage:
    """Tests for CapsuleWithLineage model."""

    def test_valid_capsule_with_lineage(self):
        """Valid capsule with lineage data creates model."""
        now = datetime.now(UTC)
        ancestor = LineageNode(
            id="ancestor123",
            version="0.1.0",
            type=CapsuleType.KNOWLEDGE,
            created_at=now,
            trust_level=TrustLevel.TRUSTED,
            depth=1,
        )
        child = LineageNode(
            id="child456",
            version="1.1.0",
            type=CapsuleType.INSIGHT,
            created_at=now,
            trust_level=TrustLevel.STANDARD,
            depth=1,
        )

        capsule = CapsuleWithLineage(
            id="cap123",
            content="Test content",
            owner_id="user456",
            lineage=[ancestor],
            children=[child],
            lineage_depth=1,
            created_at=now,
            updated_at=now,
        )

        assert len(capsule.lineage) == 1
        assert len(capsule.children) == 1
        assert capsule.lineage_depth == 1

    def test_capsule_with_lineage_defaults(self):
        """CapsuleWithLineage has sensible defaults."""
        now = datetime.now(UTC)
        capsule = CapsuleWithLineage(
            id="cap123",
            content="Test",
            owner_id="user456",
            created_at=now,
            updated_at=now,
        )

        assert capsule.lineage == []
        assert capsule.children == []
        assert capsule.lineage_depth == 0

    def test_lineage_depth_non_negative(self):
        """Lineage depth must be non-negative."""
        now = datetime.now(UTC)
        with pytest.raises(ValidationError):
            CapsuleWithLineage(
                id="cap123",
                content="Test",
                owner_id="user456",
                lineage_depth=-1,
                created_at=now,
                updated_at=now,
            )


# =============================================================================
# CapsuleSearchResult Tests
# =============================================================================


class TestCapsuleSearchResult:
    """Tests for CapsuleSearchResult model."""

    def test_valid_search_result(self):
        """Valid search result data creates model."""
        now = datetime.now(UTC)
        capsule = Capsule(
            id="cap123",
            content="Test content about machine learning",
            owner_id="user456",
            created_at=now,
            updated_at=now,
        )

        result = CapsuleSearchResult(
            capsule=capsule,
            score=0.95,
            highlights=["machine learning", "test content"],
        )

        assert result.score == 0.95
        assert len(result.highlights) == 2

    def test_score_min_bound(self):
        """Score must be at least 0.0."""
        now = datetime.now(UTC)
        capsule = Capsule(
            id="cap123",
            content="Test",
            owner_id="user456",
            created_at=now,
            updated_at=now,
        )

        with pytest.raises(ValidationError):
            CapsuleSearchResult(capsule=capsule, score=-0.1)

    def test_score_max_bound(self):
        """Score must be at most 1.0."""
        now = datetime.now(UTC)
        capsule = Capsule(
            id="cap123",
            content="Test",
            owner_id="user456",
            created_at=now,
            updated_at=now,
        )

        with pytest.raises(ValidationError):
            CapsuleSearchResult(capsule=capsule, score=1.1)

    def test_score_boundary_values(self):
        """Score boundary values (0.0, 1.0) are valid."""
        now = datetime.now(UTC)
        capsule = Capsule(
            id="cap123",
            content="Test",
            owner_id="user456",
            created_at=now,
            updated_at=now,
        )

        result_min = CapsuleSearchResult(capsule=capsule, score=0.0)
        result_max = CapsuleSearchResult(capsule=capsule, score=1.0)

        assert result_min.score == 0.0
        assert result_max.score == 1.0

    def test_search_result_defaults(self):
        """CapsuleSearchResult has sensible defaults."""
        now = datetime.now(UTC)
        capsule = Capsule(
            id="cap123",
            content="Test",
            owner_id="user456",
            created_at=now,
            updated_at=now,
        )

        result = CapsuleSearchResult(capsule=capsule, score=0.5)
        assert result.highlights == []


# =============================================================================
# CapsuleFork Tests
# =============================================================================


class TestCapsuleFork:
    """Tests for CapsuleFork model."""

    def test_valid_capsule_fork(self):
        """Valid fork request data creates model."""
        fork = CapsuleFork(
            parent_id="parent123",
            content="Modified content",
            evolution_reason="Adding more detail",
            inherit_metadata=True,
        )

        assert fork.parent_id == "parent123"
        assert fork.content == "Modified content"
        assert fork.evolution_reason == "Adding more detail"
        assert fork.inherit_metadata is True

    def test_capsule_fork_required_fields(self):
        """CapsuleFork requires parent_id and evolution_reason."""
        with pytest.raises(ValidationError):
            CapsuleFork(parent_id="parent123")  # Missing evolution_reason

        with pytest.raises(ValidationError):
            CapsuleFork(evolution_reason="A reason")  # Missing parent_id

    def test_evolution_reason_min_length(self):
        """Evolution reason must be at least 1 character."""
        with pytest.raises(ValidationError, match="String should have at least 1"):
            CapsuleFork(
                parent_id="parent123",
                evolution_reason="",
            )

    def test_evolution_reason_max_length(self):
        """Evolution reason must be at most 1000 characters."""
        with pytest.raises(ValidationError):
            CapsuleFork(
                parent_id="parent123",
                evolution_reason="a" * 1001,
            )

    def test_capsule_fork_defaults(self):
        """CapsuleFork has sensible defaults."""
        fork = CapsuleFork(
            parent_id="parent123",
            evolution_reason="A valid reason",
        )

        assert fork.content is None
        assert fork.inherit_metadata is True


# =============================================================================
# CapsuleStats Tests
# =============================================================================


class TestCapsuleStats:
    """Tests for CapsuleStats model."""

    def test_valid_capsule_stats(self):
        """Valid stats data creates model."""
        stats = CapsuleStats(
            total_count=100,
            by_type={"KNOWLEDGE": 50, "INSIGHT": 30, "CODE": 20},
            by_trust_level={"STANDARD": 70, "TRUSTED": 30},
            average_lineage_depth=2.5,
            total_views=1000,
            total_forks=50,
        )

        assert stats.total_count == 100
        assert stats.by_type["KNOWLEDGE"] == 50
        assert stats.average_lineage_depth == 2.5

    def test_capsule_stats_defaults(self):
        """CapsuleStats has sensible defaults."""
        stats = CapsuleStats()

        assert stats.total_count == 0
        assert stats.by_type == {}
        assert stats.by_trust_level == {}
        assert stats.average_lineage_depth == 0.0
        assert stats.total_views == 0
        assert stats.total_forks == 0


# =============================================================================
# IntegrityReport Tests
# =============================================================================


class TestIntegrityReport:
    """Tests for IntegrityReport model."""

    def test_valid_integrity_report(self):
        """Valid integrity report data creates model."""
        now = datetime.now(UTC)
        expected_hash = "a" * 64
        computed_hash = "a" * 64

        report = IntegrityReport(
            capsule_id="cap123",
            content_hash_valid=True,
            content_hash_expected=expected_hash,
            content_hash_computed=computed_hash,
            signature_valid=True,
            merkle_chain_valid=True,
            overall_status=IntegrityStatus.VALID,
            checked_at=now,
            details={"verification_time_ms": 15},
        )

        assert report.capsule_id == "cap123"
        assert report.content_hash_valid is True
        assert report.overall_status == IntegrityStatus.VALID

    def test_integrity_report_required_fields(self):
        """IntegrityReport requires essential fields."""
        with pytest.raises(ValidationError):
            IntegrityReport(
                capsule_id="cap123",
                content_hash_valid=True,
                # Missing overall_status and checked_at
            )

    def test_integrity_report_corrupted_status(self):
        """IntegrityReport can report corruption."""
        now = datetime.now(UTC)
        report = IntegrityReport(
            capsule_id="cap123",
            content_hash_valid=False,
            content_hash_expected="a" * 64,
            content_hash_computed="b" * 64,  # Different
            overall_status=IntegrityStatus.CORRUPTED,
            checked_at=now,
        )

        assert report.content_hash_valid is False
        assert report.overall_status == IntegrityStatus.CORRUPTED

    def test_integrity_report_defaults(self):
        """IntegrityReport has sensible defaults."""
        now = datetime.now(UTC)
        report = IntegrityReport(
            capsule_id="cap123",
            content_hash_valid=True,
            overall_status=IntegrityStatus.VALID,
            checked_at=now,
        )

        assert report.content_hash_expected is None
        assert report.content_hash_computed is None
        assert report.signature_valid is None
        assert report.merkle_chain_valid is None
        assert report.details == {}


# =============================================================================
# LineageIntegrityReport Tests
# =============================================================================


class TestLineageIntegrityReport:
    """Tests for LineageIntegrityReport model."""

    def test_valid_lineage_integrity_report(self):
        """Valid lineage integrity report data creates model."""
        now = datetime.now(UTC)
        report = LineageIntegrityReport(
            capsule_id="cap123",
            chain_length=5,
            all_hashes_valid=True,
            merkle_chain_valid=True,
            broken_at=None,
            verified_capsules=["cap1", "cap2", "cap3", "cap4", "cap123"],
            failed_capsules=[],
            checked_at=now,
        )

        assert report.capsule_id == "cap123"
        assert report.chain_length == 5
        assert report.all_hashes_valid is True
        assert report.merkle_chain_valid is True
        assert len(report.verified_capsules) == 5

    def test_lineage_integrity_report_broken_chain(self):
        """LineageIntegrityReport can report broken chain."""
        now = datetime.now(UTC)
        report = LineageIntegrityReport(
            capsule_id="cap123",
            chain_length=5,
            all_hashes_valid=False,
            merkle_chain_valid=False,
            broken_at="cap3",
            verified_capsules=["cap1", "cap2"],
            failed_capsules=["cap3", "cap4", "cap123"],
            checked_at=now,
        )

        assert report.all_hashes_valid is False
        assert report.merkle_chain_valid is False
        assert report.broken_at == "cap3"
        assert len(report.failed_capsules) == 3

    def test_chain_length_non_negative(self):
        """Chain length must be non-negative."""
        now = datetime.now(UTC)
        with pytest.raises(ValidationError):
            LineageIntegrityReport(
                capsule_id="cap123",
                chain_length=-1,
                all_hashes_valid=True,
                merkle_chain_valid=True,
                checked_at=now,
            )

    def test_lineage_integrity_report_defaults(self):
        """LineageIntegrityReport has sensible defaults."""
        now = datetime.now(UTC)
        report = LineageIntegrityReport(
            capsule_id="cap123",
            chain_length=0,
            all_hashes_valid=True,
            merkle_chain_valid=True,
            checked_at=now,
        )

        assert report.broken_at is None
        assert report.verified_capsules == []
        assert report.failed_capsules == []


# =============================================================================
# SHA256_PATTERN Tests
# =============================================================================


class TestSHA256Pattern:
    """Tests for SHA256_PATTERN regex."""

    def test_valid_sha256_hashes(self):
        """Valid SHA-256 hashes match the pattern."""
        valid_hashes = [
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "a" * 64,
            "0" * 64,
            "f" * 64,
            "0123456789abcdef" * 4,
        ]

        for hash_value in valid_hashes:
            assert SHA256_PATTERN.match(hash_value) is not None, f"Expected {hash_value} to match"

    def test_invalid_sha256_hashes(self):
        """Invalid SHA-256 hashes do not match the pattern."""
        invalid_hashes = [
            "abc",  # Too short
            "a" * 63,  # One character too short
            "a" * 65,  # One character too long
            "A" * 64,  # Uppercase
            "g" * 64,  # Invalid hex char
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b85G",  # G is invalid
            "",  # Empty
            " " + "a" * 64,  # Leading space
            "a" * 64 + " ",  # Trailing space
        ]

        for hash_value in invalid_hashes:
            assert SHA256_PATTERN.match(hash_value) is None, f"Expected {hash_value} not to match"


# =============================================================================
# Edge Cases and Integration Tests
# =============================================================================


class TestEdgeCases:
    """Edge case and integration tests."""

    def test_capsule_with_all_fields_populated(self):
        """Capsule with all fields populated works correctly."""
        now = datetime.now(UTC)
        capsule = CapsuleInDB(
            id="cap123",
            content="Full content here with all fields set.",
            type=CapsuleType.INSIGHT,
            title="Complete Capsule",
            summary="A summary of the complete capsule",
            tags=["complete", "test"],
            metadata={"source": "test", "priority": 1},
            version="2.1.0",
            owner_id="user456",
            trust_level=TrustLevel.TRUSTED,
            parent_id="parent789",
            is_archived=False,
            view_count=100,
            fork_count=5,
            embedding=[0.1] * 1536,
            content_hash="a" * 64,
            integrity_status=IntegrityStatus.VALID,
            integrity_verified_at=now,
            signature="base64signature==",
            signature_algorithm="Ed25519",
            signed_at=now,
            signed_by="signer123",
            parent_content_hash="b" * 64,
            merkle_root="c" * 64,
            created_at=now,
            updated_at=now,
        )

        assert capsule.id == "cap123"
        assert capsule.trust_level == TrustLevel.TRUSTED
        assert len(capsule.embedding) == 1536

    def test_capsule_base_content_whitespace_stripped(self):
        """Content whitespace is stripped (from ForgeModel config)."""
        capsule = CapsuleBase(content="  test content  ")
        assert capsule.content == "test content"

    def test_unicode_content_handling(self):
        """Unicode content is handled correctly."""
        unicode_content = "Hello, World!"
        capsule = CapsuleBase(content=unicode_content)
        assert capsule.content == unicode_content

    def test_special_characters_in_tags(self):
        """Special characters in tags are handled."""
        capsule = CapsuleBase(
            content="test",
            tags=["c++", "c#", "node.js"],
        )
        # Tags are lowercased
        assert capsule.tags == ["c++", "c#", "node.js"]

    def test_metadata_with_lists(self):
        """Metadata with list values works correctly."""
        capsule = CapsuleBase(
            content="test",
            metadata={
                "authors": ["alice", "bob"],
                "versions": [1, 2, 3],
            },
        )
        assert capsule.metadata["authors"] == ["alice", "bob"]

    def test_metadata_with_nested_list_of_dicts(self):
        """Metadata with nested lists of dicts is validated."""
        # Valid case
        capsule = CapsuleBase(
            content="test",
            metadata={
                "items": [{"name": "item1"}, {"name": "item2"}],
            },
        )
        assert len(capsule.metadata["items"]) == 2

        # Invalid case: forbidden key in nested dict
        with pytest.raises(ValidationError, match="Forbidden keys"):
            CapsuleBase(
                content="test",
                metadata={
                    "items": [{"name": "valid"}, {"__proto__": "invalid"}],
                },
            )

    def test_empty_embedding_list_invalid(self):
        """Empty embedding list has invalid dimensions."""
        now = datetime.now(UTC)
        with pytest.raises(ValidationError, match="valid dimensions"):
            CapsuleInDB(
                id="cap123",
                content="Test",
                owner_id="user456",
                embedding=[],
                created_at=now,
                updated_at=now,
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
