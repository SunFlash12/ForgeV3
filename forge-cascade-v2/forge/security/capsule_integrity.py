"""
Capsule Integrity Service

Provides cryptographic integrity verification for capsules:
- Content hash verification (SHA-256)
- Digital signatures (Ed25519)
- Merkle tree lineage verification

Security Features:
- Constant-time comparison for all hash/signature verification
- Ed25519 for modern, fast, secure signatures
- Immutable parent_content_hash snapshots at fork time
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from datetime import datetime
from typing import TYPE_CHECKING

import structlog
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

if TYPE_CHECKING:
    from forge.models.capsule import Capsule

logger = structlog.get_logger(__name__)


class IntegrityError(Exception):
    """Base exception for integrity verification failures."""

    pass


class ContentHashMismatchError(IntegrityError):
    """Raised when content hash doesn't match stored hash."""

    def __init__(self, capsule_id: str, expected: str, computed: str):
        self.capsule_id = capsule_id
        self.expected = expected
        self.computed = computed
        super().__init__(
            f"Content hash mismatch for capsule {capsule_id}: "
            f"expected {expected[:16]}..., got {computed[:16]}..."
        )


class SignatureVerificationError(IntegrityError):
    """Raised when signature verification fails."""

    def __init__(self, capsule_id: str, reason: str):
        self.capsule_id = capsule_id
        self.reason = reason
        super().__init__(f"Signature verification failed for capsule {capsule_id}: {reason}")


class MerkleChainError(IntegrityError):
    """Raised when Merkle chain verification fails."""

    def __init__(self, capsule_id: str, broken_at: str | None = None):
        self.capsule_id = capsule_id
        self.broken_at = broken_at
        msg = f"Merkle chain broken for capsule {capsule_id}"
        if broken_at:
            msg += f" at {broken_at}"
        super().__init__(msg)


class CapsuleIntegrityService:
    """
    Service for capsule content hashing, signing, and verification.

    This service provides cryptographic integrity guarantees for capsules:
    1. Content Hash: SHA-256 hash computed on create, verified on read
    2. Digital Signatures: Ed25519 signatures proving authorship
    3. Merkle Tree: Verifiable hash chain for DERIVED_FROM lineage

    All verification uses constant-time comparison to prevent timing attacks.
    """

    # ═══════════════════════════════════════════════════════════════════════════
    # CONTENT HASH (Phase 1)
    # ═══════════════════════════════════════════════════════════════════════════

    @staticmethod
    def compute_content_hash(content: str) -> str:
        """
        Compute SHA-256 hash of capsule content.

        Args:
            content: The capsule content string

        Returns:
            Lowercase hex-encoded SHA-256 hash (64 characters)
        """
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    @staticmethod
    def verify_content_hash(content: str, expected_hash: str) -> bool:
        """
        Verify content matches expected hash using constant-time comparison.

        This prevents timing attacks that could reveal information about
        the expected hash through response time variations.

        Args:
            content: The capsule content string
            expected_hash: The expected SHA-256 hash (64 hex chars)

        Returns:
            True if hash matches, False otherwise
        """
        computed = hashlib.sha256(content.encode("utf-8")).hexdigest()
        # Use secrets.compare_digest for constant-time comparison
        return secrets.compare_digest(computed, expected_hash)

    @staticmethod
    def verify_content_hash_detailed(
        content: str, expected_hash: str
    ) -> tuple[bool, str, str]:
        """
        Verify content hash with detailed results.

        Args:
            content: The capsule content string
            expected_hash: The expected SHA-256 hash

        Returns:
            Tuple of (is_valid, expected_hash, computed_hash)
        """
        computed = hashlib.sha256(content.encode("utf-8")).hexdigest()
        is_valid = secrets.compare_digest(computed, expected_hash)
        return is_valid, expected_hash, computed

    # ═══════════════════════════════════════════════════════════════════════════
    # DIGITAL SIGNATURES (Phase 2)
    # ═══════════════════════════════════════════════════════════════════════════

    @staticmethod
    def generate_keypair() -> tuple[bytes, bytes]:
        """
        Generate Ed25519 keypair for capsule signing.

        Ed25519 is chosen for:
        - Modern elliptic curve security
        - Fast signature generation and verification
        - Small key and signature sizes (32-byte keys, 64-byte signatures)
        - Deterministic signatures (same message + key = same signature)

        Returns:
            Tuple of (private_key_bytes, public_key_bytes)
            Both are 32 bytes raw.
        """
        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        return (
            private_key.private_bytes_raw(),
            public_key.public_bytes_raw(),
        )

    @staticmethod
    def keypair_to_base64(private_key: bytes, public_key: bytes) -> tuple[str, str]:
        """
        Encode keypair as base64 strings for storage/transport.

        Args:
            private_key: Raw private key bytes (32 bytes)
            public_key: Raw public key bytes (32 bytes)

        Returns:
            Tuple of (private_key_b64, public_key_b64)
        """
        return (
            base64.b64encode(private_key).decode("utf-8"),
            base64.b64encode(public_key).decode("utf-8"),
        )

    @staticmethod
    def sign_capsule(content_hash: str, private_key_bytes: bytes) -> str:
        """
        Sign capsule content hash with Ed25519 private key.

        The signature is over the content_hash (not raw content) to:
        - Keep signature operation fast regardless of content size
        - Allow signature verification without full content access
        - Support content-addressed storage patterns

        Args:
            content_hash: SHA-256 hash of capsule content (64 hex chars)
            private_key_bytes: Raw Ed25519 private key (32 bytes)

        Returns:
            Base64-encoded signature (88 characters)
        """
        private_key = Ed25519PrivateKey.from_private_bytes(private_key_bytes)
        signature = private_key.sign(content_hash.encode("utf-8"))
        return base64.b64encode(signature).decode("utf-8")

    @staticmethod
    def sign_capsule_with_b64_key(content_hash: str, private_key_b64: str) -> str:
        """
        Sign capsule with base64-encoded private key.

        Convenience method for when private key is stored as base64.

        Args:
            content_hash: SHA-256 hash of capsule content
            private_key_b64: Base64-encoded Ed25519 private key

        Returns:
            Base64-encoded signature
        """
        private_key_bytes = base64.b64decode(private_key_b64)
        return CapsuleIntegrityService.sign_capsule(content_hash, private_key_bytes)

    @staticmethod
    def verify_signature(
        content_hash: str,
        signature_b64: str,
        public_key_b64: str,
    ) -> bool:
        """
        Verify Ed25519 signature against content hash.

        Args:
            content_hash: SHA-256 hash of capsule content (64 hex chars)
            signature_b64: Base64-encoded Ed25519 signature
            public_key_b64: Base64-encoded Ed25519 public key

        Returns:
            True if signature is valid, False otherwise
        """
        try:
            signature = base64.b64decode(signature_b64)
            public_key_bytes = base64.b64decode(public_key_b64)
            public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
            public_key.verify(signature, content_hash.encode("utf-8"))
            return True
        except Exception as e:
            logger.debug(
                "signature_verification_failed",
                error=str(e),
                content_hash_prefix=content_hash[:16] if content_hash else None,
            )
            return False

    @staticmethod
    def verify_signature_with_raw_key(
        content_hash: str,
        signature_b64: str,
        public_key_bytes: bytes,
    ) -> bool:
        """
        Verify signature with raw public key bytes.

        Args:
            content_hash: SHA-256 hash of capsule content
            signature_b64: Base64-encoded signature
            public_key_bytes: Raw Ed25519 public key (32 bytes)

        Returns:
            True if signature is valid
        """
        try:
            signature = base64.b64decode(signature_b64)
            public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
            public_key.verify(signature, content_hash.encode("utf-8"))
            return True
        except Exception:
            return False

    # ═══════════════════════════════════════════════════════════════════════════
    # MERKLE TREE LINEAGE (Phase 3)
    # ═══════════════════════════════════════════════════════════════════════════

    @staticmethod
    def compute_merkle_root(
        content_hash: str,
        parent_merkle_root: str | None,
    ) -> str:
        """
        Compute Merkle root for capsule lineage.

        The Merkle root creates a verifiable chain:
        - Root capsule: merkle_root = content_hash
        - Child capsule: merkle_root = hash(content_hash + ":" + parent_merkle_root)

        This allows verification that:
        1. The capsule content hasn't changed
        2. The lineage chain is intact from root to leaf
        3. No intermediate capsules have been modified

        Args:
            content_hash: SHA-256 hash of this capsule's content
            parent_merkle_root: Parent capsule's merkle_root (None for root capsules)

        Returns:
            SHA-256 hash representing the Merkle root
        """
        if parent_merkle_root is None:
            # Root capsule - merkle root equals content hash
            return content_hash

        # Child capsule - chain with parent's merkle root
        combined = f"{content_hash}:{parent_merkle_root}"
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()

    @staticmethod
    def verify_merkle_root(
        content_hash: str,
        parent_merkle_root: str | None,
        expected_merkle_root: str,
    ) -> bool:
        """
        Verify a capsule's Merkle root is correct.

        Uses constant-time comparison to prevent timing attacks.

        Args:
            content_hash: SHA-256 hash of capsule content
            parent_merkle_root: Parent's merkle_root (None for root)
            expected_merkle_root: The stored merkle_root to verify

        Returns:
            True if Merkle root is valid
        """
        computed = CapsuleIntegrityService.compute_merkle_root(
            content_hash, parent_merkle_root
        )
        return secrets.compare_digest(computed, expected_merkle_root)

    @staticmethod
    def verify_merkle_chain(
        capsules: list[Capsule],
    ) -> tuple[bool, str | None]:
        """
        Verify entire lineage chain from root to leaf.

        Capsules must be ordered from root (oldest ancestor) to leaf.

        Args:
            capsules: List of capsules ordered root -> leaf

        Returns:
            Tuple of (is_valid, error_capsule_id)
            error_capsule_id is the ID of the first capsule where chain breaks
        """
        if not capsules:
            return True, None

        for i, capsule in enumerate(capsules):
            # Get content hash - compute if not stored
            content_hash = getattr(capsule, "content_hash", None)
            if not content_hash:
                content_hash = CapsuleIntegrityService.compute_content_hash(
                    capsule.content
                )

            # Get merkle root - must be stored
            merkle_root = getattr(capsule, "merkle_root", None)
            if not merkle_root:
                # No merkle root stored - can't verify chain
                logger.warning(
                    "merkle_chain_verification_skipped",
                    capsule_id=capsule.id,
                    reason="no merkle_root stored",
                )
                continue

            if i == 0:
                # Root capsule - merkle root should equal content hash
                expected = content_hash
            else:
                # Child capsule - chain with parent's merkle root
                parent = capsules[i - 1]
                parent_merkle_root = getattr(parent, "merkle_root", None)
                if not parent_merkle_root:
                    # Can't verify without parent's merkle root
                    continue
                expected = CapsuleIntegrityService.compute_merkle_root(
                    content_hash, parent_merkle_root
                )

            if not secrets.compare_digest(merkle_root, expected):
                return False, capsule.id

        return True, None

    # ═══════════════════════════════════════════════════════════════════════════
    # COMPREHENSIVE VERIFICATION
    # ═══════════════════════════════════════════════════════════════════════════

    @staticmethod
    def verify_capsule_integrity(
        capsule: Capsule,
        public_key_b64: str | None = None,
        parent_merkle_root: str | None = None,
    ) -> dict:
        """
        Perform comprehensive integrity verification on a capsule.

        Args:
            capsule: The capsule to verify
            public_key_b64: Signer's public key (for signature verification)
            parent_merkle_root: Parent's merkle root (for chain verification)

        Returns:
            Dictionary with verification results
        """
        now = datetime.utcnow()
        result = {
            "capsule_id": capsule.id,
            "checked_at": now,
            "content_hash_valid": False,
            "content_hash_expected": None,
            "content_hash_computed": None,
            "signature_valid": None,
            "merkle_root_valid": None,
            "overall_valid": False,
            "errors": [],
        }

        # 1. Verify content hash
        stored_hash = getattr(capsule, "content_hash", None)
        computed_hash = CapsuleIntegrityService.compute_content_hash(capsule.content)
        result["content_hash_computed"] = computed_hash

        if stored_hash:
            result["content_hash_expected"] = stored_hash
            result["content_hash_valid"] = secrets.compare_digest(
                computed_hash, stored_hash
            )
            if not result["content_hash_valid"]:
                result["errors"].append("Content hash mismatch")
        else:
            # No hash stored - cannot verify but not necessarily invalid
            result["content_hash_valid"] = True
            result["errors"].append("No content_hash stored - verification skipped")

        # 2. Verify signature (if signed)
        signature = getattr(capsule, "signature", None)
        if signature and public_key_b64:
            content_hash = stored_hash or computed_hash
            result["signature_valid"] = CapsuleIntegrityService.verify_signature(
                content_hash, signature, public_key_b64
            )
            if not result["signature_valid"]:
                result["errors"].append("Signature verification failed")
        elif signature and not public_key_b64:
            result["signature_valid"] = None
            result["errors"].append("Signature present but no public key provided")

        # 3. Verify Merkle root (if has lineage)
        merkle_root = getattr(capsule, "merkle_root", None)
        if merkle_root:
            content_hash = stored_hash or computed_hash
            result["merkle_root_valid"] = CapsuleIntegrityService.verify_merkle_root(
                content_hash, parent_merkle_root, merkle_root
            )
            if not result["merkle_root_valid"]:
                result["errors"].append("Merkle root verification failed")

        # Overall status
        result["overall_valid"] = (
            result["content_hash_valid"]
            and (result["signature_valid"] is not False)
            and (result["merkle_root_valid"] is not False)
        )

        return result


# Convenience singleton access
_integrity_service: CapsuleIntegrityService | None = None


def get_integrity_service() -> CapsuleIntegrityService:
    """Get or create the integrity service singleton."""
    global _integrity_service
    if _integrity_service is None:
        _integrity_service = CapsuleIntegrityService()
    return _integrity_service
