"""
Key Management Service

Manages Ed25519 signing keys for capsule signatures.
Supports 4 key storage strategies:
1. SERVER_CUSTODY: Server stores encrypted private key
2. CLIENT_ONLY: User manages keys externally
3. PASSWORD_DERIVED: Keys derived from password using HKDF
4. NONE: No signing enabled

Security Features:
- AES-256-GCM encryption for server-custodied keys
- HKDF for password-derived keys with unique salt
- Constant-time operations where applicable
"""

from __future__ import annotations

import base64
import os
import secrets
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from forge.models.user import KeyStorageStrategy

if TYPE_CHECKING:
    pass

logger = structlog.get_logger(__name__)


class KeyManagementError(Exception):
    """Base exception for key management errors."""

    pass


class KeyNotFoundError(KeyManagementError):
    """User has no signing keys configured."""

    pass


class KeyDecryptionError(KeyManagementError):
    """Failed to decrypt private key (wrong password or corrupted)."""

    pass


class KeyDerivationError(KeyManagementError):
    """Failed to derive key from password."""

    pass


class InvalidKeyError(KeyManagementError):
    """Key format or length is invalid."""

    pass


class SigningKeyInfo:
    """Information about a user's signing key configuration."""

    def __init__(
        self,
        strategy: KeyStorageStrategy,
        public_key_b64: str | None,
        created_at: datetime | None,
        can_sign: bool,
    ):
        self.strategy = strategy
        self.public_key_b64 = public_key_b64
        self.created_at = created_at
        self.can_sign = can_sign

    def to_dict(self) -> dict:
        return {
            "strategy": self.strategy.value,
            "public_key": self.public_key_b64,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "can_sign": self.can_sign,
        }


class KeyManagementService:
    """
    Service for managing Ed25519 signing keys.

    Supports multiple key storage strategies to balance security and usability.
    """

    # AES-256-GCM parameters
    AES_KEY_SIZE = 32  # 256 bits
    AES_NONCE_SIZE = 12  # 96 bits (GCM standard)
    AES_TAG_SIZE = 16  # 128 bits

    # HKDF parameters
    HKDF_SALT_SIZE = 32  # 256 bits
    HKDF_INFO = b"forge-capsule-signing-key-v1"

    # ═══════════════════════════════════════════════════════════════════════════
    # KEY GENERATION
    # ═══════════════════════════════════════════════════════════════════════════

    @staticmethod
    def generate_keypair() -> tuple[bytes, bytes]:
        """
        Generate a new Ed25519 keypair.

        Returns:
            Tuple of (private_key_bytes, public_key_bytes)
            Both are 32 bytes.
        """
        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        return (
            private_key.private_bytes_raw(),
            public_key.public_bytes_raw(),
        )

    @staticmethod
    def keypair_to_b64(
        private_key: bytes, public_key: bytes
    ) -> tuple[str, str]:
        """
        Encode keypair as base64 strings.

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
    def public_key_from_private(private_key: bytes) -> bytes:
        """
        Derive public key from private key.

        Args:
            private_key: Raw Ed25519 private key (32 bytes)

        Returns:
            Raw public key bytes (32 bytes)
        """
        private = Ed25519PrivateKey.from_private_bytes(private_key)
        return private.public_key().public_bytes_raw()

    # ═══════════════════════════════════════════════════════════════════════════
    # SERVER CUSTODY (Strategy 1)
    # Private key encrypted with AES-256-GCM using password-derived key
    # ═══════════════════════════════════════════════════════════════════════════

    @staticmethod
    def _derive_encryption_key(password: str, salt: bytes) -> bytes:
        """
        Derive AES-256 encryption key from password using HKDF.

        Args:
            password: User's password
            salt: Random salt (32 bytes)

        Returns:
            32-byte encryption key
        """
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=KeyManagementService.AES_KEY_SIZE,
            salt=salt,
            info=b"forge-key-encryption-v1",
        )
        return hkdf.derive(password.encode("utf-8"))

    @staticmethod
    def encrypt_private_key(private_key: bytes, password: str) -> str:
        """
        Encrypt private key for server custody storage.

        Uses AES-256-GCM with a password-derived key.
        Output format: base64(salt || nonce || ciphertext || tag)

        Args:
            private_key: Raw Ed25519 private key (32 bytes)
            password: User's password for encryption

        Returns:
            Base64-encoded encrypted key (salt + nonce + ciphertext + tag)
        """
        # Generate random salt and nonce
        salt = os.urandom(KeyManagementService.HKDF_SALT_SIZE)
        nonce = os.urandom(KeyManagementService.AES_NONCE_SIZE)

        # Derive encryption key from password
        enc_key = KeyManagementService._derive_encryption_key(password, salt)

        # Encrypt with AES-256-GCM
        aesgcm = AESGCM(enc_key)
        ciphertext = aesgcm.encrypt(nonce, private_key, None)

        # Combine: salt || nonce || ciphertext (includes tag)
        combined = salt + nonce + ciphertext

        return base64.b64encode(combined).decode("utf-8")

    @staticmethod
    def decrypt_private_key(encrypted_b64: str, password: str) -> bytes:
        """
        Decrypt server-custodied private key.

        Args:
            encrypted_b64: Base64-encoded encrypted key
            password: User's password

        Returns:
            Raw private key bytes (32 bytes)

        Raises:
            KeyDecryptionError: If decryption fails
        """
        try:
            combined = base64.b64decode(encrypted_b64)

            # Extract components
            salt = combined[: KeyManagementService.HKDF_SALT_SIZE]
            nonce = combined[
                KeyManagementService.HKDF_SALT_SIZE : KeyManagementService.HKDF_SALT_SIZE
                + KeyManagementService.AES_NONCE_SIZE
            ]
            ciphertext = combined[
                KeyManagementService.HKDF_SALT_SIZE
                + KeyManagementService.AES_NONCE_SIZE :
            ]

            # Derive encryption key
            enc_key = KeyManagementService._derive_encryption_key(password, salt)

            # Decrypt
            aesgcm = AESGCM(enc_key)
            private_key = aesgcm.decrypt(nonce, ciphertext, None)

            return private_key

        except Exception as e:
            logger.warning("key_decryption_failed", error=str(e))
            raise KeyDecryptionError("Failed to decrypt private key") from e

    @classmethod
    def setup_server_custody(cls, password: str) -> dict:
        """
        Set up signing keys with server custody.

        Generates keypair and encrypts private key with password.

        Args:
            password: User's password for key encryption

        Returns:
            Dictionary with:
            - public_key_b64: Base64 public key (store in DB)
            - encrypted_private_key: Encrypted private key (store in DB)
            - created_at: Timestamp
        """
        private_key, public_key = cls.generate_keypair()
        encrypted = cls.encrypt_private_key(private_key, password)

        return {
            "strategy": KeyStorageStrategy.SERVER_CUSTODY,
            "public_key_b64": base64.b64encode(public_key).decode("utf-8"),
            "encrypted_private_key": encrypted,
            "created_at": datetime.now(UTC),
        }

    # ═══════════════════════════════════════════════════════════════════════════
    # CLIENT ONLY (Strategy 2)
    # Server only stores public key; user manages private key
    # ═══════════════════════════════════════════════════════════════════════════

    @classmethod
    def setup_client_only(cls, public_key_b64: str) -> dict:
        """
        Set up signing keys with client-only storage.

        User provides their public key; private key stays with user.

        Args:
            public_key_b64: Base64-encoded Ed25519 public key from user

        Returns:
            Dictionary with:
            - public_key_b64: Validated public key
            - created_at: Timestamp

        Raises:
            InvalidKeyError: If public key is invalid
        """
        # Validate the public key
        try:
            public_key_bytes = base64.b64decode(public_key_b64)
            if len(public_key_bytes) != 32:
                raise InvalidKeyError("Public key must be 32 bytes")
            # Verify it's a valid Ed25519 public key
            Ed25519PublicKey.from_public_bytes(public_key_bytes)
        except Exception as e:
            raise InvalidKeyError(f"Invalid Ed25519 public key: {e}") from e

        return {
            "strategy": KeyStorageStrategy.CLIENT_ONLY,
            "public_key_b64": public_key_b64,
            "created_at": datetime.now(UTC),
        }

    # ═══════════════════════════════════════════════════════════════════════════
    # PASSWORD DERIVED (Strategy 3)
    # Keys deterministically derived from password + salt
    # ═══════════════════════════════════════════════════════════════════════════

    @classmethod
    def derive_keypair_from_password(
        cls, password: str, salt: bytes | None = None
    ) -> tuple[bytes, bytes, bytes]:
        """
        Derive Ed25519 keypair from password using HKDF.

        Same password + salt always produces same keypair.
        Useful for key recovery without storing private key.

        Args:
            password: User's password
            salt: Optional salt (generated if not provided)

        Returns:
            Tuple of (private_key, public_key, salt)
        """
        if salt is None:
            salt = os.urandom(cls.HKDF_SALT_SIZE)

        # Use HKDF to derive 32 bytes for Ed25519 seed
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,  # Ed25519 private key size
            salt=salt,
            info=cls.HKDF_INFO,
        )
        seed = hkdf.derive(password.encode("utf-8"))

        # Create Ed25519 keypair from seed
        private_key = Ed25519PrivateKey.from_private_bytes(seed)
        public_key = private_key.public_key()

        return (
            private_key.private_bytes_raw(),
            public_key.public_bytes_raw(),
            salt,
        )

    @classmethod
    def setup_password_derived(cls, password: str) -> dict:
        """
        Set up signing keys derived from password.

        Stores only public key and salt. Private key is derived
        from password when needed.

        Args:
            password: User's password

        Returns:
            Dictionary with:
            - public_key_b64: Base64 public key
            - salt_b64: Base64 salt for key derivation
            - created_at: Timestamp
        """
        private_key, public_key, salt = cls.derive_keypair_from_password(password)

        return {
            "strategy": KeyStorageStrategy.PASSWORD_DERIVED,
            "public_key_b64": base64.b64encode(public_key).decode("utf-8"),
            "salt_b64": base64.b64encode(salt).decode("utf-8"),
            "created_at": datetime.now(UTC),
        }

    @classmethod
    def get_private_key_password_derived(
        cls, password: str, salt_b64: str
    ) -> bytes:
        """
        Recover private key from password and salt.

        Args:
            password: User's password
            salt_b64: Base64-encoded salt from setup

        Returns:
            Raw private key bytes
        """
        salt = base64.b64decode(salt_b64)
        private_key, _, _ = cls.derive_keypair_from_password(password, salt)
        return private_key

    # ═══════════════════════════════════════════════════════════════════════════
    # UNIFIED INTERFACE
    # ═══════════════════════════════════════════════════════════════════════════

    @classmethod
    def setup_signing_keys(
        cls,
        strategy: KeyStorageStrategy,
        password: str | None = None,
        public_key_b64: str | None = None,
    ) -> dict:
        """
        Set up signing keys using the specified strategy.

        Args:
            strategy: Key storage strategy
            password: Required for SERVER_CUSTODY and PASSWORD_DERIVED
            public_key_b64: Required for CLIENT_ONLY

        Returns:
            Dictionary with keys to store in user record

        Raises:
            ValueError: If required parameters missing
            InvalidKeyError: If public key invalid
        """
        if strategy == KeyStorageStrategy.NONE:
            return {
                "strategy": KeyStorageStrategy.NONE,
                "created_at": datetime.now(UTC),
            }

        if strategy == KeyStorageStrategy.SERVER_CUSTODY:
            if not password:
                raise ValueError("Password required for SERVER_CUSTODY strategy")
            return cls.setup_server_custody(password)

        if strategy == KeyStorageStrategy.CLIENT_ONLY:
            if not public_key_b64:
                raise ValueError("Public key required for CLIENT_ONLY strategy")
            return cls.setup_client_only(public_key_b64)

        if strategy == KeyStorageStrategy.PASSWORD_DERIVED:
            if not password:
                raise ValueError("Password required for PASSWORD_DERIVED strategy")
            return cls.setup_password_derived(password)

        raise ValueError(f"Unknown strategy: {strategy}")

    @classmethod
    def get_private_key(
        cls,
        strategy: KeyStorageStrategy,
        password: str | None = None,
        encrypted_private_key: str | None = None,
        salt_b64: str | None = None,
        client_private_key_b64: str | None = None,
    ) -> bytes:
        """
        Retrieve private key based on storage strategy.

        Args:
            strategy: How keys are stored
            password: User's password (for SERVER_CUSTODY, PASSWORD_DERIVED)
            encrypted_private_key: Encrypted key (for SERVER_CUSTODY)
            salt_b64: Salt (for PASSWORD_DERIVED)
            client_private_key_b64: Private key from client (for CLIENT_ONLY)

        Returns:
            Raw private key bytes (32 bytes)

        Raises:
            KeyNotFoundError: If keys not configured
            KeyDecryptionError: If decryption fails
            ValueError: If required parameters missing
        """
        if strategy == KeyStorageStrategy.NONE:
            raise KeyNotFoundError("User has no signing keys configured")

        if strategy == KeyStorageStrategy.SERVER_CUSTODY:
            if not password or not encrypted_private_key:
                raise ValueError(
                    "Password and encrypted_private_key required for SERVER_CUSTODY"
                )
            return cls.decrypt_private_key(encrypted_private_key, password)

        if strategy == KeyStorageStrategy.CLIENT_ONLY:
            if not client_private_key_b64:
                raise ValueError("Private key required for CLIENT_ONLY strategy")
            try:
                private_key = base64.b64decode(client_private_key_b64)
                if len(private_key) != 32:
                    raise InvalidKeyError("Private key must be 32 bytes")
                return private_key
            except Exception as e:
                raise InvalidKeyError(f"Invalid private key: {e}") from e

        if strategy == KeyStorageStrategy.PASSWORD_DERIVED:
            if not password or not salt_b64:
                raise ValueError("Password and salt required for PASSWORD_DERIVED")
            return cls.get_private_key_password_derived(password, salt_b64)

        raise ValueError(f"Unknown strategy: {strategy}")


# Convenience singleton
_key_service: KeyManagementService | None = None


def get_key_management_service() -> KeyManagementService:
    """Get or create key management service singleton."""
    global _key_service
    if _key_service is None:
        _key_service = KeyManagementService()
    return _key_service
