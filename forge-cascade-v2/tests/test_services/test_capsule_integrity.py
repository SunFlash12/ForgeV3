"""
Capsule Integrity Service Tests for Forge Cascade V2

Comprehensive tests for capsule integrity verification including:
- Content hash computation and verification
- Digital signatures (Ed25519)
- Merkle tree lineage verification
"""

import base64
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from forge.security.capsule_integrity import (
    CapsuleIntegrityService,
    ContentHashMismatchError,
    MerkleChainError,
    SignatureVerificationError,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def integrity_service():
    """Create integrity service instance."""
    return CapsuleIntegrityService()


@pytest.fixture
def sample_content():
    """Sample capsule content for testing."""
    return "This is sample capsule content for testing integrity verification."


@pytest.fixture
def sample_keypair():
    """Generate sample Ed25519 keypair."""
    private_key, public_key = CapsuleIntegrityService.generate_keypair()
    private_b64, public_b64 = CapsuleIntegrityService.keypair_to_base64(private_key, public_key)
    return {
        "private_bytes": private_key,
        "public_bytes": public_key,
        "private_b64": private_b64,
        "public_b64": public_b64,
    }


@dataclass
class MockCapsule:
    """Mock capsule for testing."""

    id: str
    content: str
    content_hash: str | None = None
    merkle_root: str | None = None
    signature: str | None = None


# =============================================================================
# Content Hash Tests
# =============================================================================


class TestContentHash:
    """Tests for content hash computation and verification."""

    def test_compute_content_hash_basic(self, sample_content):
        """Content hash computation produces SHA-256 hex string."""
        hash_value = CapsuleIntegrityService.compute_content_hash(sample_content)

        assert len(hash_value) == 64  # SHA-256 hex digest
        assert all(c in "0123456789abcdef" for c in hash_value)

    def test_compute_content_hash_deterministic(self, sample_content):
        """Same content always produces same hash."""
        hash1 = CapsuleIntegrityService.compute_content_hash(sample_content)
        hash2 = CapsuleIntegrityService.compute_content_hash(sample_content)

        assert hash1 == hash2

    def test_compute_content_hash_different_content(self):
        """Different content produces different hashes."""
        hash1 = CapsuleIntegrityService.compute_content_hash("Content A")
        hash2 = CapsuleIntegrityService.compute_content_hash("Content B")

        assert hash1 != hash2

    def test_compute_content_hash_empty_string(self):
        """Empty string produces valid hash."""
        hash_value = CapsuleIntegrityService.compute_content_hash("")

        assert len(hash_value) == 64
        # Known SHA-256 of empty string
        expected = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        assert hash_value == expected

    def test_compute_content_hash_unicode(self):
        """Unicode content produces valid hash."""
        hash_value = CapsuleIntegrityService.compute_content_hash("Hello, World!")

        assert len(hash_value) == 64

    def test_verify_content_hash_valid(self, sample_content):
        """Valid content hash verifies successfully."""
        expected_hash = CapsuleIntegrityService.compute_content_hash(sample_content)

        assert CapsuleIntegrityService.verify_content_hash(sample_content, expected_hash) is True

    def test_verify_content_hash_invalid(self, sample_content):
        """Modified content fails hash verification."""
        expected_hash = CapsuleIntegrityService.compute_content_hash(sample_content)
        modified_content = sample_content + " modified"

        assert CapsuleIntegrityService.verify_content_hash(modified_content, expected_hash) is False

    def test_verify_content_hash_wrong_hash(self, sample_content):
        """Wrong hash fails verification."""
        wrong_hash = "a" * 64  # Valid format but wrong value

        assert CapsuleIntegrityService.verify_content_hash(sample_content, wrong_hash) is False

    def test_verify_content_hash_detailed(self, sample_content):
        """Detailed verification returns expected values."""
        expected_hash = CapsuleIntegrityService.compute_content_hash(sample_content)

        is_valid, expected, computed = CapsuleIntegrityService.verify_content_hash_detailed(
            sample_content, expected_hash
        )

        assert is_valid is True
        assert expected == expected_hash
        assert computed == expected_hash

    def test_verify_content_hash_detailed_mismatch(self, sample_content):
        """Detailed verification shows mismatch."""
        wrong_hash = "b" * 64

        is_valid, expected, computed = CapsuleIntegrityService.verify_content_hash_detailed(
            sample_content, wrong_hash
        )

        assert is_valid is False
        assert expected == wrong_hash
        assert computed != wrong_hash


# =============================================================================
# Digital Signature Tests
# =============================================================================


class TestDigitalSignatures:
    """Tests for Ed25519 digital signatures."""

    def test_generate_keypair(self):
        """Keypair generation produces valid keys."""
        private_key, public_key = CapsuleIntegrityService.generate_keypair()

        assert len(private_key) == 32  # Ed25519 private key size
        assert len(public_key) == 32  # Ed25519 public key size

    def test_generate_keypair_unique(self):
        """Each keypair is unique."""
        pair1 = CapsuleIntegrityService.generate_keypair()
        pair2 = CapsuleIntegrityService.generate_keypair()

        assert pair1[0] != pair2[0]  # Private keys differ
        assert pair1[1] != pair2[1]  # Public keys differ

    def test_keypair_to_base64(self, sample_keypair):
        """Keypair converts to base64 correctly."""
        private_b64 = sample_keypair["private_b64"]
        public_b64 = sample_keypair["public_b64"]

        # Should be valid base64
        assert base64.b64decode(private_b64) == sample_keypair["private_bytes"]
        assert base64.b64decode(public_b64) == sample_keypair["public_bytes"]

    def test_sign_capsule(self, sample_content, sample_keypair):
        """Capsule signing produces valid signature."""
        content_hash = CapsuleIntegrityService.compute_content_hash(sample_content)

        signature = CapsuleIntegrityService.sign_capsule(
            content_hash, sample_keypair["private_bytes"]
        )

        # Signature should be base64-encoded
        sig_bytes = base64.b64decode(signature)
        assert len(sig_bytes) == 64  # Ed25519 signature size

    def test_sign_capsule_with_b64_key(self, sample_content, sample_keypair):
        """Capsule signing with base64 key works."""
        content_hash = CapsuleIntegrityService.compute_content_hash(sample_content)

        signature = CapsuleIntegrityService.sign_capsule_with_b64_key(
            content_hash, sample_keypair["private_b64"]
        )

        assert len(base64.b64decode(signature)) == 64

    def test_sign_capsule_deterministic(self, sample_content, sample_keypair):
        """Ed25519 signatures are deterministic."""
        content_hash = CapsuleIntegrityService.compute_content_hash(sample_content)

        sig1 = CapsuleIntegrityService.sign_capsule(content_hash, sample_keypair["private_bytes"])
        sig2 = CapsuleIntegrityService.sign_capsule(content_hash, sample_keypair["private_bytes"])

        assert sig1 == sig2

    def test_verify_signature_valid(self, sample_content, sample_keypair):
        """Valid signature verifies successfully."""
        content_hash = CapsuleIntegrityService.compute_content_hash(sample_content)
        signature = CapsuleIntegrityService.sign_capsule(
            content_hash, sample_keypair["private_bytes"]
        )

        assert (
            CapsuleIntegrityService.verify_signature(
                content_hash, signature, sample_keypair["public_b64"]
            )
            is True
        )

    def test_verify_signature_wrong_content(self, sample_content, sample_keypair):
        """Signature fails with different content."""
        content_hash = CapsuleIntegrityService.compute_content_hash(sample_content)
        signature = CapsuleIntegrityService.sign_capsule(
            content_hash, sample_keypair["private_bytes"]
        )

        wrong_hash = CapsuleIntegrityService.compute_content_hash("Different content")

        assert (
            CapsuleIntegrityService.verify_signature(
                wrong_hash, signature, sample_keypair["public_b64"]
            )
            is False
        )

    def test_verify_signature_wrong_key(self, sample_content, sample_keypair):
        """Signature fails with different public key."""
        content_hash = CapsuleIntegrityService.compute_content_hash(sample_content)
        signature = CapsuleIntegrityService.sign_capsule(
            content_hash, sample_keypair["private_bytes"]
        )

        # Generate different keypair
        _, other_public = CapsuleIntegrityService.generate_keypair()
        _, other_public_b64 = CapsuleIntegrityService.keypair_to_base64(b"\x00" * 32, other_public)

        assert (
            CapsuleIntegrityService.verify_signature(content_hash, signature, other_public_b64)
            is False
        )

    def test_verify_signature_invalid_format(self, sample_content, sample_keypair):
        """Invalid signature format fails gracefully."""
        content_hash = CapsuleIntegrityService.compute_content_hash(sample_content)

        # Invalid base64
        assert (
            CapsuleIntegrityService.verify_signature(
                content_hash, "not-valid-base64!", sample_keypair["public_b64"]
            )
            is False
        )

    def test_verify_signature_with_raw_key(self, sample_content, sample_keypair):
        """Signature verification with raw key bytes works."""
        content_hash = CapsuleIntegrityService.compute_content_hash(sample_content)
        signature = CapsuleIntegrityService.sign_capsule(
            content_hash, sample_keypair["private_bytes"]
        )

        assert (
            CapsuleIntegrityService.verify_signature_with_raw_key(
                content_hash, signature, sample_keypair["public_bytes"]
            )
            is True
        )


# =============================================================================
# Merkle Tree Tests
# =============================================================================


class TestMerkleTree:
    """Tests for Merkle tree lineage verification."""

    def test_compute_merkle_root_no_parent(self, sample_content):
        """Root capsule Merkle root equals content hash."""
        content_hash = CapsuleIntegrityService.compute_content_hash(sample_content)

        merkle_root = CapsuleIntegrityService.compute_merkle_root(
            content_hash, parent_merkle_root=None
        )

        assert merkle_root == content_hash

    def test_compute_merkle_root_with_parent(self, sample_content):
        """Child capsule Merkle root chains with parent."""
        content_hash = CapsuleIntegrityService.compute_content_hash(sample_content)
        parent_merkle_root = "a" * 64

        merkle_root = CapsuleIntegrityService.compute_merkle_root(content_hash, parent_merkle_root)

        # Should be different from both content hash and parent
        assert merkle_root != content_hash
        assert merkle_root != parent_merkle_root
        assert len(merkle_root) == 64

    def test_compute_merkle_root_deterministic(self, sample_content):
        """Merkle root computation is deterministic."""
        content_hash = CapsuleIntegrityService.compute_content_hash(sample_content)
        parent_merkle_root = "b" * 64

        root1 = CapsuleIntegrityService.compute_merkle_root(content_hash, parent_merkle_root)
        root2 = CapsuleIntegrityService.compute_merkle_root(content_hash, parent_merkle_root)

        assert root1 == root2

    def test_verify_merkle_root_valid(self, sample_content):
        """Valid Merkle root verifies successfully."""
        content_hash = CapsuleIntegrityService.compute_content_hash(sample_content)
        parent_merkle_root = "c" * 64

        expected_merkle_root = CapsuleIntegrityService.compute_merkle_root(
            content_hash, parent_merkle_root
        )

        assert (
            CapsuleIntegrityService.verify_merkle_root(
                content_hash, parent_merkle_root, expected_merkle_root
            )
            is True
        )

    def test_verify_merkle_root_invalid(self, sample_content):
        """Invalid Merkle root fails verification."""
        content_hash = CapsuleIntegrityService.compute_content_hash(sample_content)
        parent_merkle_root = "d" * 64
        wrong_merkle_root = "e" * 64

        assert (
            CapsuleIntegrityService.verify_merkle_root(
                content_hash, parent_merkle_root, wrong_merkle_root
            )
            is False
        )

    def test_verify_merkle_chain_empty(self):
        """Empty chain is valid."""
        is_valid, error_id = CapsuleIntegrityService.verify_merkle_chain([])

        assert is_valid is True
        assert error_id is None

    def test_verify_merkle_chain_single_root(self):
        """Single root capsule chain is valid."""
        content = "Root capsule content"
        content_hash = CapsuleIntegrityService.compute_content_hash(content)
        merkle_root = CapsuleIntegrityService.compute_merkle_root(content_hash, None)

        capsule = MockCapsule(
            id="root1",
            content=content,
            content_hash=content_hash,
            merkle_root=merkle_root,
        )

        is_valid, error_id = CapsuleIntegrityService.verify_merkle_chain([capsule])

        assert is_valid is True
        assert error_id is None

    def test_verify_merkle_chain_valid_lineage(self):
        """Valid parent-child chain verifies."""
        # Create root
        root_content = "Root content"
        root_hash = CapsuleIntegrityService.compute_content_hash(root_content)
        root_merkle = CapsuleIntegrityService.compute_merkle_root(root_hash, None)

        root = MockCapsule(
            id="root1",
            content=root_content,
            content_hash=root_hash,
            merkle_root=root_merkle,
        )

        # Create child
        child_content = "Child content"
        child_hash = CapsuleIntegrityService.compute_content_hash(child_content)
        child_merkle = CapsuleIntegrityService.compute_merkle_root(child_hash, root_merkle)

        child = MockCapsule(
            id="child1",
            content=child_content,
            content_hash=child_hash,
            merkle_root=child_merkle,
        )

        is_valid, error_id = CapsuleIntegrityService.verify_merkle_chain([root, child])

        assert is_valid is True
        assert error_id is None

    def test_verify_merkle_chain_broken(self):
        """Broken chain returns error capsule ID."""
        # Create root
        root_content = "Root content"
        root_hash = CapsuleIntegrityService.compute_content_hash(root_content)
        root_merkle = CapsuleIntegrityService.compute_merkle_root(root_hash, None)

        root = MockCapsule(
            id="root1",
            content=root_content,
            content_hash=root_hash,
            merkle_root=root_merkle,
        )

        # Create child with wrong merkle root
        child_content = "Child content"
        child_hash = CapsuleIntegrityService.compute_content_hash(child_content)

        child = MockCapsule(
            id="child1",
            content=child_content,
            content_hash=child_hash,
            merkle_root="wrong_merkle_root" + "0" * (64 - 17),  # Wrong value
        )

        is_valid, error_id = CapsuleIntegrityService.verify_merkle_chain([root, child])

        assert is_valid is False
        assert error_id == "child1"


# =============================================================================
# Comprehensive Verification Tests
# =============================================================================


class TestCapsuleIntegrityVerification:
    """Tests for comprehensive capsule integrity verification."""

    def test_verify_capsule_integrity_valid(self, sample_content, sample_keypair):
        """Valid capsule passes all integrity checks."""
        content_hash = CapsuleIntegrityService.compute_content_hash(sample_content)
        merkle_root = CapsuleIntegrityService.compute_merkle_root(content_hash, None)
        signature = CapsuleIntegrityService.sign_capsule(
            content_hash, sample_keypair["private_bytes"]
        )

        capsule = MockCapsule(
            id="valid1",
            content=sample_content,
            content_hash=content_hash,
            merkle_root=merkle_root,
            signature=signature,
        )

        result = CapsuleIntegrityService.verify_capsule_integrity(
            capsule,
            public_key_b64=sample_keypair["public_b64"],
            parent_merkle_root=None,
        )

        assert result["overall_valid"] is True
        assert result["content_hash_valid"] is True
        assert result["signature_valid"] is True
        assert result["merkle_root_valid"] is True
        assert len(result["errors"]) == 0

    def test_verify_capsule_integrity_content_mismatch(self, sample_content):
        """Content hash mismatch is detected."""
        content_hash = CapsuleIntegrityService.compute_content_hash(sample_content)

        capsule = MockCapsule(
            id="invalid1",
            content="Modified content",  # Different from hash
            content_hash=content_hash,
        )

        result = CapsuleIntegrityService.verify_capsule_integrity(capsule)

        assert result["overall_valid"] is False
        assert result["content_hash_valid"] is False
        assert "Content hash mismatch" in result["errors"]

    def test_verify_capsule_integrity_invalid_signature(self, sample_content, sample_keypair):
        """Invalid signature is detected."""
        content_hash = CapsuleIntegrityService.compute_content_hash(sample_content)

        # Sign with one key, verify with another
        _, other_public = CapsuleIntegrityService.generate_keypair()
        _, other_public_b64 = CapsuleIntegrityService.keypair_to_base64(b"\x00" * 32, other_public)

        signature = CapsuleIntegrityService.sign_capsule(
            content_hash, sample_keypair["private_bytes"]
        )

        capsule = MockCapsule(
            id="invalid2",
            content=sample_content,
            content_hash=content_hash,
            signature=signature,
        )

        result = CapsuleIntegrityService.verify_capsule_integrity(
            capsule,
            public_key_b64=other_public_b64,  # Wrong key
        )

        assert result["overall_valid"] is False
        assert result["signature_valid"] is False
        assert "Signature verification failed" in result["errors"]

    def test_verify_capsule_integrity_no_hash_stored(self, sample_content):
        """Capsule without stored hash still validates."""
        capsule = MockCapsule(
            id="nohash1",
            content=sample_content,
            content_hash=None,  # No hash stored
        )

        result = CapsuleIntegrityService.verify_capsule_integrity(capsule)

        # Should not fail, just note that verification was skipped
        assert result["content_hash_valid"] is True
        assert "verification skipped" in str(result["errors"])

    def test_verify_capsule_integrity_signature_without_key(self, sample_content, sample_keypair):
        """Signature without public key is noted but not failed."""
        content_hash = CapsuleIntegrityService.compute_content_hash(sample_content)
        signature = CapsuleIntegrityService.sign_capsule(
            content_hash, sample_keypair["private_bytes"]
        )

        capsule = MockCapsule(
            id="nokey1",
            content=sample_content,
            content_hash=content_hash,
            signature=signature,
        )

        result = CapsuleIntegrityService.verify_capsule_integrity(
            capsule,
            public_key_b64=None,  # No key provided
        )

        # Should note the issue but not fail overall
        assert result["signature_valid"] is None
        assert "no public key provided" in str(result["errors"])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
