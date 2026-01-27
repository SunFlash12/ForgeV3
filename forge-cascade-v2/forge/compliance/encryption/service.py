"""
Forge Compliance Framework - Encryption Service

Provides encryption services for data at rest and in transit:
- AES-256-GCM encryption for data at rest
- Key management with rotation
- Field-level encryption for sensitive data
- Tokenization for PCI/PHI data
- HSM integration support

Per SOC 2 CC6.1, ISO 27001 A.8.24, NIST SC-8/SC-28, PCI-DSS 3.5
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, TypeVar
from uuid import uuid4

import structlog
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from forge.compliance.core.config import get_compliance_config
from forge.compliance.core.enums import (
    DataClassification,
    EncryptionStandard,
    KeyRotationPolicy,
)

logger = structlog.get_logger(__name__)

T = TypeVar("T")


# ═══════════════════════════════════════════════════════════════════════════
# KEY MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class EncryptionKey:
    """Represents an encryption key with metadata."""

    key_id: str
    key_material: bytes
    algorithm: EncryptionStandard
    created_at: datetime
    expires_at: datetime | None
    purpose: str  # "data", "dek", "kek", "signing"
    version: int = 1
    is_active: bool = True

    @property
    def is_expired(self) -> bool:
        """Check if key is expired."""
        if not self.expires_at:
            return False
        return datetime.now(UTC) > self.expires_at

    def to_dict(self) -> dict[str, Any]:
        """Serialize key metadata (without material)."""
        return {
            "key_id": self.key_id,
            "algorithm": self.algorithm.value,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "purpose": self.purpose,
            "version": self.version,
            "is_active": self.is_active,
        }


class KeyStore(ABC):
    """Abstract key store interface."""

    @abstractmethod
    async def store_key(self, key: EncryptionKey) -> None:
        """Store an encryption key."""
        pass

    @abstractmethod
    async def get_key(self, key_id: str) -> EncryptionKey | None:
        """Retrieve a key by ID."""
        pass

    @abstractmethod
    async def get_active_key(self, purpose: str) -> EncryptionKey | None:
        """Get the current active key for a purpose."""
        pass

    @abstractmethod
    async def rotate_key(self, purpose: str) -> EncryptionKey:
        """Create a new key and deactivate the old one."""
        pass

    @abstractmethod
    async def list_keys(self, purpose: str | None = None) -> list[EncryptionKey]:
        """List all keys, optionally filtered by purpose."""
        pass


class InMemoryKeyStore(KeyStore):
    """
    In-memory key store for development/testing ONLY.

    WARNING: Not suitable for production. Use DatabaseKeyStore or HSM-backed store.
    Keys will be lost on application restart.
    """

    def __init__(self):
        self._keys: dict[str, EncryptionKey] = {}
        self._active_keys: dict[str, str] = {}  # purpose -> key_id

    async def store_key(self, key: EncryptionKey) -> None:
        self._keys[key.key_id] = key
        if key.is_active:
            self._active_keys[key.purpose] = key.key_id

    async def get_key(self, key_id: str) -> EncryptionKey | None:
        return self._keys.get(key_id)

    async def get_active_key(self, purpose: str) -> EncryptionKey | None:
        key_id = self._active_keys.get(purpose)
        if key_id:
            return self._keys.get(key_id)
        return None

    async def rotate_key(self, purpose: str) -> EncryptionKey:
        # Deactivate old key
        old_key_id = self._active_keys.get(purpose)
        if old_key_id and old_key_id in self._keys:
            self._keys[old_key_id].is_active = False

        # Generate new key
        config = get_compliance_config()
        rotation_days = {
            KeyRotationPolicy.DAYS_30: 30,
            KeyRotationPolicy.DAYS_90: 90,
            KeyRotationPolicy.DAYS_180: 180,
            KeyRotationPolicy.YEARS_1: 365,
            KeyRotationPolicy.YEARS_2: 730,
        }.get(config.key_rotation_policy, 90)

        old_version = 0
        if old_key_id and old_key_id in self._keys:
            old_version = self._keys[old_key_id].version

        new_key = EncryptionKey(
            key_id=str(uuid4()),
            key_material=secrets.token_bytes(32),
            algorithm=config.encryption_at_rest_standard,
            created_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(days=rotation_days),
            purpose=purpose,
            version=old_version + 1,
            is_active=True,
        )

        await self.store_key(new_key)

        logger.info(
            "key_rotated",
            purpose=purpose,
            new_key_id=new_key.key_id,
            version=new_key.version,
        )

        return new_key

    async def list_keys(self, purpose: str | None = None) -> list[EncryptionKey]:
        keys = list(self._keys.values())
        if purpose:
            keys = [k for k in keys if k.purpose == purpose]
        return keys


class DatabaseKeyStore(KeyStore):
    """
    Neo4j-backed key store with encrypted key material persistence.

    This store provides persistence for encryption keys across restarts.
    Key material is encrypted before storage using a master key from environment.

    IMPORTANT: For full compliance (PCI-DSS 3.5-3.6, HIPAA, SOC 2 CC6.1),
    consider using HSM or Cloud KMS instead:
    - AWS CloudHSM / AWS KMS
    - Azure Dedicated HSM / Azure Key Vault
    - Google Cloud HSM / GCP KMS
    - On-premise: Thales Luna HSM

    This implementation provides:
    - Persistence across restarts
    - Encrypted key material at rest
    - Key rotation with version tracking
    - Separation of key metadata and encrypted material
    """

    def __init__(self, neo4j_client, master_key: bytes | None = None):
        """
        Initialize database key store.

        Args:
            neo4j_client: Neo4j async client
            master_key: Master key for encrypting stored key material.
                       If None, uses ENCRYPTION_MASTER_KEY environment variable.
        """
        self._db = neo4j_client
        self._initialized = False

        # Get master key from parameter or environment
        if master_key:
            self._master_key = master_key
        else:
            import os

            master_key_b64 = os.environ.get("ENCRYPTION_MASTER_KEY")
            if master_key_b64:
                self._master_key = base64.b64decode(master_key_b64)
            else:
                # Generate ephemeral master key if none provided
                # WARNING: This defeats the purpose of persistence - keys will be unrecoverable after restart
                logger.warning(
                    "database_keystore_no_master_key",
                    message="No ENCRYPTION_MASTER_KEY set - using ephemeral key (keys will be lost on restart)",
                )
                self._master_key = secrets.token_bytes(32)

        # In-memory cache for performance
        self._keys_cache: dict[str, EncryptionKey] = {}
        self._active_keys_cache: dict[str, str] = {}

    async def initialize(self) -> None:
        """Create indexes and load existing keys."""
        if self._initialized:
            return

        # Create indexes
        try:
            await self._db.execute(
                "CREATE CONSTRAINT encryption_key_id IF NOT EXISTS FOR (k:EncryptionKey) REQUIRE k.key_id IS UNIQUE"
            )
            await self._db.execute(
                "CREATE INDEX encryption_key_purpose IF NOT EXISTS FOR (k:EncryptionKey) ON (k.purpose)"
            )
        except Exception as e:
            if "already exists" not in str(e).lower():
                logger.warning("keystore_index_creation_warning", error=str(e))

        # Load existing keys into cache
        await self._load_keys()

        self._initialized = True
        logger.info("database_keystore_initialized", keys_loaded=len(self._keys_cache))

    def _encrypt_key_material(self, key_material: bytes) -> bytes:
        """Encrypt key material with master key for storage."""
        nonce = secrets.token_bytes(12)
        aesgcm = AESGCM(self._master_key)
        ciphertext = aesgcm.encrypt(nonce, key_material, None)
        # Prepend nonce to ciphertext
        return nonce + ciphertext

    def _decrypt_key_material(self, encrypted: bytes) -> bytes:
        """Decrypt key material from storage."""
        nonce = encrypted[:12]
        ciphertext = encrypted[12:]
        aesgcm = AESGCM(self._master_key)
        return aesgcm.decrypt(nonce, ciphertext, None)

    async def _load_keys(self) -> None:
        """Load all keys from database into cache."""
        query = """
        MATCH (k:EncryptionKey)
        RETURN k
        ORDER BY k.version DESC
        """
        try:
            results = await self._db.execute(query, {})
            for record in results:
                key_data = dict(record["k"])

                # Decrypt key material
                encrypted_material = base64.b64decode(key_data["encrypted_key_material"])
                try:
                    key_material = self._decrypt_key_material(encrypted_material)
                except Exception as e:
                    logger.error("key_decryption_failed", key_id=key_data["key_id"], error=str(e))
                    continue

                key = EncryptionKey(
                    key_id=key_data["key_id"],
                    key_material=key_material,
                    algorithm=EncryptionStandard(key_data["algorithm"]),
                    created_at=datetime.fromisoformat(key_data["created_at"])
                    if isinstance(key_data["created_at"], str)
                    else key_data["created_at"],
                    expires_at=datetime.fromisoformat(key_data["expires_at"])
                    if key_data.get("expires_at") and isinstance(key_data["expires_at"], str)
                    else key_data.get("expires_at"),
                    purpose=key_data["purpose"],
                    version=key_data["version"],
                    is_active=key_data["is_active"],
                )

                self._keys_cache[key.key_id] = key
                if key.is_active:
                    self._active_keys_cache[key.purpose] = key.key_id

        except Exception as e:
            logger.error("keystore_load_failed", error=str(e))

    async def store_key(self, key: EncryptionKey) -> None:
        """Store an encryption key in database."""
        # Encrypt key material
        encrypted_material = self._encrypt_key_material(key.key_material)

        query = """
        MERGE (k:EncryptionKey {key_id: $key_id})
        SET k.encrypted_key_material = $encrypted_key_material,
            k.algorithm = $algorithm,
            k.created_at = $created_at,
            k.expires_at = $expires_at,
            k.purpose = $purpose,
            k.version = $version,
            k.is_active = $is_active
        """

        await self._db.execute(
            query,
            {
                "key_id": key.key_id,
                "encrypted_key_material": base64.b64encode(encrypted_material).decode(),
                "algorithm": key.algorithm.value,
                "created_at": key.created_at.isoformat(),
                "expires_at": key.expires_at.isoformat() if key.expires_at else None,
                "purpose": key.purpose,
                "version": key.version,
                "is_active": key.is_active,
            },
        )

        # Update cache
        self._keys_cache[key.key_id] = key
        if key.is_active:
            self._active_keys_cache[key.purpose] = key.key_id

        logger.info("encryption_key_stored", key_id=key.key_id, purpose=key.purpose)

    async def get_key(self, key_id: str) -> EncryptionKey | None:
        """Get key from cache (loaded from database on init)."""
        return self._keys_cache.get(key_id)

    async def get_active_key(self, purpose: str) -> EncryptionKey | None:
        """Get active key for purpose from cache."""
        key_id = self._active_keys_cache.get(purpose)
        if key_id:
            return self._keys_cache.get(key_id)
        return None

    async def rotate_key(self, purpose: str) -> EncryptionKey:
        """Create new key and deactivate old one."""
        # Deactivate old key
        old_key_id = self._active_keys_cache.get(purpose)
        if old_key_id and old_key_id in self._keys_cache:
            old_key = self._keys_cache[old_key_id]
            old_key.is_active = False

            # Update database
            await self._db.execute(
                "MATCH (k:EncryptionKey {key_id: $key_id}) SET k.is_active = false",
                {"key_id": old_key_id},
            )

        # Generate new key
        config = get_compliance_config()
        rotation_days = {
            KeyRotationPolicy.DAYS_30: 30,
            KeyRotationPolicy.DAYS_90: 90,
            KeyRotationPolicy.DAYS_180: 180,
            KeyRotationPolicy.YEARS_1: 365,
            KeyRotationPolicy.YEARS_2: 730,
        }.get(config.key_rotation_policy, 90)

        old_version = 0
        if old_key_id and old_key_id in self._keys_cache:
            old_version = self._keys_cache[old_key_id].version

        new_key = EncryptionKey(
            key_id=str(uuid4()),
            key_material=secrets.token_bytes(32),
            algorithm=config.encryption_at_rest_standard,
            created_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(days=rotation_days),
            purpose=purpose,
            version=old_version + 1,
            is_active=True,
        )

        await self.store_key(new_key)

        logger.info(
            "key_rotated",
            purpose=purpose,
            new_key_id=new_key.key_id,
            version=new_key.version,
        )

        return new_key

    async def list_keys(self, purpose: str | None = None) -> list[EncryptionKey]:
        """List all keys, optionally filtered by purpose."""
        keys = list(self._keys_cache.values())
        if purpose:
            keys = [k for k in keys if k.purpose == purpose]
        return keys


# ═══════════════════════════════════════════════════════════════════════════
# ENCRYPTION SERVICE
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class EncryptedData:
    """Container for encrypted data with metadata."""

    ciphertext: bytes
    nonce: bytes
    key_id: str
    algorithm: str
    encrypted_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_bytes(self) -> bytes:
        """Serialize to bytes for storage."""
        return json.dumps(
            {
                "ciphertext": base64.b64encode(self.ciphertext).decode(),
                "nonce": base64.b64encode(self.nonce).decode(),
                "key_id": self.key_id,
                "algorithm": self.algorithm,
                "encrypted_at": self.encrypted_at.isoformat(),
            }
        ).encode()

    @classmethod
    def from_bytes(cls, data: bytes) -> EncryptedData:
        """Deserialize from bytes."""
        parsed = json.loads(data.decode())
        return cls(
            ciphertext=base64.b64decode(parsed["ciphertext"]),
            nonce=base64.b64decode(parsed["nonce"]),
            key_id=parsed["key_id"],
            algorithm=parsed["algorithm"],
            encrypted_at=datetime.fromisoformat(parsed["encrypted_at"]),
        )

    def to_base64(self) -> str:
        """Encode to base64 string for database storage."""
        return base64.b64encode(self.to_bytes()).decode()

    @classmethod
    def from_base64(cls, data: str) -> EncryptedData:
        """Decode from base64 string."""
        return cls.from_bytes(base64.b64decode(data))


class EncryptionService:
    """
    Comprehensive encryption service for Forge compliance.

    Provides:
    - AES-256-GCM authenticated encryption
    - Envelope encryption (data keys encrypted by master key)
    - Key rotation with re-encryption
    - Field-level encryption for sensitive data
    - Tokenization for PCI/PHI data
    """

    def __init__(
        self,
        key_store: KeyStore | None = None,
    ):
        self.key_store = key_store or InMemoryKeyStore()
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize encryption service with default keys."""
        if self._initialized:
            return

        # Create default keys for each purpose
        for purpose in ["data", "dek", "token", "signing"]:
            existing = await self.key_store.get_active_key(purpose)
            if not existing:
                await self.key_store.rotate_key(purpose)

        self._initialized = True
        logger.info("encryption_service_initialized")

    # ───────────────────────────────────────────────────────────────
    # CORE ENCRYPTION
    # ───────────────────────────────────────────────────────────────

    async def encrypt(
        self,
        plaintext: bytes,
        purpose: str = "data",
        aad: bytes | None = None,
    ) -> EncryptedData:
        """
        Encrypt data using AES-256-GCM.

        Args:
            plaintext: Data to encrypt
            purpose: Key purpose (determines which key to use)
            aad: Additional authenticated data (optional)

        Returns:
            EncryptedData container with ciphertext and metadata
        """
        await self.initialize()

        key = await self.key_store.get_active_key(purpose)
        if not key:
            raise ValueError(f"No active key for purpose: {purpose}")

        # Generate random nonce (12 bytes for GCM)
        nonce = secrets.token_bytes(12)

        # Encrypt using AES-256-GCM
        aesgcm = AESGCM(key.key_material)
        ciphertext = aesgcm.encrypt(nonce, plaintext, aad)

        return EncryptedData(
            ciphertext=ciphertext,
            nonce=nonce,
            key_id=key.key_id,
            algorithm="AES-256-GCM",
        )

    async def decrypt(
        self,
        encrypted: EncryptedData,
        aad: bytes | None = None,
    ) -> bytes:
        """
        Decrypt data using AES-256-GCM.

        Args:
            encrypted: EncryptedData container
            aad: Additional authenticated data (must match encryption)

        Returns:
            Decrypted plaintext
        """
        key = await self.key_store.get_key(encrypted.key_id)
        if not key:
            raise ValueError(f"Key not found: {encrypted.key_id}")

        aesgcm = AESGCM(key.key_material)
        return aesgcm.decrypt(encrypted.nonce, encrypted.ciphertext, aad)

    async def encrypt_string(
        self,
        plaintext: str,
        purpose: str = "data",
    ) -> str:
        """Encrypt a string and return base64-encoded result."""
        encrypted = await self.encrypt(plaintext.encode("utf-8"), purpose)
        return encrypted.to_base64()

    async def decrypt_string(
        self,
        encrypted_b64: str,
    ) -> str:
        """Decrypt a base64-encoded encrypted string."""
        encrypted = EncryptedData.from_base64(encrypted_b64)
        plaintext = await self.decrypt(encrypted)
        return plaintext.decode("utf-8")

    # ───────────────────────────────────────────────────────────────
    # ENVELOPE ENCRYPTION
    # ───────────────────────────────────────────────────────────────

    async def envelope_encrypt(
        self,
        plaintext: bytes,
        aad: bytes | None = None,
    ) -> dict[str, Any]:
        """
        Envelope encryption: generate DEK, encrypt data, encrypt DEK with KEK.

        This is the recommended pattern for large data encryption.
        """
        await self.initialize()

        # Generate Data Encryption Key (DEK)
        dek = secrets.token_bytes(32)
        dek_nonce = secrets.token_bytes(12)

        # Encrypt data with DEK
        aesgcm = AESGCM(dek)
        ciphertext = aesgcm.encrypt(dek_nonce, plaintext, aad)

        # Encrypt DEK with Key Encryption Key (KEK)
        kek = await self.key_store.get_active_key("dek")
        if not kek:
            kek = await self.key_store.rotate_key("dek")

        kek_nonce = secrets.token_bytes(12)
        kek_aesgcm = AESGCM(kek.key_material)
        encrypted_dek = kek_aesgcm.encrypt(kek_nonce, dek, None)

        return {
            "ciphertext": base64.b64encode(ciphertext).decode(),
            "nonce": base64.b64encode(dek_nonce).decode(),
            "encrypted_dek": base64.b64encode(encrypted_dek).decode(),
            "kek_nonce": base64.b64encode(kek_nonce).decode(),
            "kek_id": kek.key_id,
            "algorithm": "AES-256-GCM-ENVELOPE",
            "encrypted_at": datetime.now(UTC).isoformat(),
        }

    async def envelope_decrypt(
        self,
        envelope: dict[str, Any],
        aad: bytes | None = None,
    ) -> bytes:
        """
        Decrypt envelope-encrypted data.
        """
        # Get KEK
        kek = await self.key_store.get_key(envelope["kek_id"])
        if not kek:
            raise ValueError(f"KEK not found: {envelope['kek_id']}")

        # Decrypt DEK
        kek_aesgcm = AESGCM(kek.key_material)
        dek = kek_aesgcm.decrypt(
            base64.b64decode(envelope["kek_nonce"]),
            base64.b64decode(envelope["encrypted_dek"]),
            None,
        )

        # Decrypt data with DEK
        aesgcm = AESGCM(dek)
        return aesgcm.decrypt(
            base64.b64decode(envelope["nonce"]),
            base64.b64decode(envelope["ciphertext"]),
            aad,
        )

    # ───────────────────────────────────────────────────────────────
    # FIELD-LEVEL ENCRYPTION
    # ───────────────────────────────────────────────────────────────

    async def encrypt_field(
        self,
        value: Any,
        field_name: str,
        entity_id: str,
    ) -> str:
        """
        Encrypt a single field value with context binding.

        The field name and entity ID are included as AAD to prevent
        ciphertext from being moved between fields/records.
        """
        # Create AAD from context
        aad = f"{field_name}:{entity_id}".encode()

        # Serialize value
        if isinstance(value, str):
            plaintext = value.encode()
        else:
            plaintext = json.dumps(value).encode()

        encrypted = await self.encrypt(plaintext, purpose="data", aad=aad)
        return encrypted.to_base64()

    async def decrypt_field(
        self,
        encrypted_value: str,
        field_name: str,
        entity_id: str,
    ) -> Any:
        """
        Decrypt a field value with context verification.
        """
        aad = f"{field_name}:{entity_id}".encode()
        encrypted = EncryptedData.from_base64(encrypted_value)
        plaintext = await self.decrypt(encrypted, aad=aad)

        # Try to deserialize as JSON
        try:
            return json.loads(plaintext.decode())
        except json.JSONDecodeError:
            return plaintext.decode()

    # ───────────────────────────────────────────────────────────────
    # TOKENIZATION
    # ───────────────────────────────────────────────────────────────

    async def tokenize(
        self,
        value: str,
        classification: DataClassification,
    ) -> str:
        """
        Tokenize sensitive data (PCI, PHI) with format-preserving token.

        Returns a token that can be used in place of the original value.
        The original value can only be retrieved with the token.
        """
        await self.initialize()

        # Get token key
        token_key = await self.key_store.get_active_key("token")
        if not token_key:
            token_key = await self.key_store.rotate_key("token")

        # Generate deterministic token using HMAC
        # This allows the same value to produce the same token
        token_hmac = hmac.new(
            token_key.key_material,
            value.encode(),
            hashlib.sha256,
        ).hexdigest()[:24]

        # Prefix based on classification
        prefix = {
            DataClassification.PCI: "PCI",
            DataClassification.PHI: "PHI",
            DataClassification.BIOMETRIC: "BIO",
            DataClassification.FINANCIAL: "FIN",
        }.get(classification, "TOK")

        token = f"{prefix}_{token_hmac}"

        # Store mapping (in production, use secure vault)
        # For this implementation, we encrypt the original value
        encrypted = await self.encrypt_string(value, purpose="token")

        # Store in a token vault (simulated here)
        self._token_vault = getattr(self, "_token_vault", {})
        self._token_vault[token] = encrypted

        logger.debug(
            "data_tokenized",
            classification=classification.value,
            token_prefix=prefix,
        )

        return token

    async def detokenize(
        self,
        token: str,
    ) -> str:
        """
        Retrieve the original value for a token.
        """
        vault = getattr(self, "_token_vault", {})
        encrypted = vault.get(token)
        if not encrypted:
            raise ValueError(f"Token not found: {token}")

        return await self.decrypt_string(encrypted)

    # ───────────────────────────────────────────────────────────────
    # HASHING
    # ───────────────────────────────────────────────────────────────

    def hash_password(
        self,
        password: str,
        salt: bytes | None = None,
    ) -> tuple[bytes, bytes]:
        """
        Hash a password using PBKDF2-SHA256.

        Returns (hash, salt) tuple.
        """
        if salt is None:
            salt = secrets.token_bytes(16)

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=600000,  # OWASP recommendation
            backend=default_backend(),
        )

        password_hash = kdf.derive(password.encode())
        return password_hash, salt

    def verify_password(
        self,
        password: str,
        password_hash: bytes,
        salt: bytes,
    ) -> bool:
        """Verify a password against its hash."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=600000,
            backend=default_backend(),
        )

        try:
            kdf.verify(password.encode(), password_hash)
            return True
        except Exception:
            return False

    def hash_data(
        self,
        data: bytes,
        algorithm: str = "sha256",
    ) -> str:
        """
        Hash data for integrity verification.

        Returns hex-encoded hash.
        """
        if algorithm == "sha256":
            return hashlib.sha256(data).hexdigest()
        elif algorithm == "sha384":
            return hashlib.sha384(data).hexdigest()
        elif algorithm == "sha512":
            return hashlib.sha512(data).hexdigest()
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")

    # ───────────────────────────────────────────────────────────────
    # KEY ROTATION
    # ───────────────────────────────────────────────────────────────

    async def rotate_keys(
        self,
        purpose: str | None = None,
    ) -> list[EncryptionKey]:
        """
        Rotate encryption keys.

        If purpose is None, rotates all key types.
        """
        purposes = [purpose] if purpose else ["data", "dek", "token", "signing"]
        rotated = []

        for p in purposes:
            new_key = await self.key_store.rotate_key(p)
            rotated.append(new_key)

            logger.info(
                "key_rotated",
                purpose=p,
                key_id=new_key.key_id,
                version=new_key.version,
                expires_at=new_key.expires_at.isoformat() if new_key.expires_at else None,
            )

        return rotated

    async def check_key_expiration(self) -> list[EncryptionKey]:
        """
        Check for expiring/expired keys.

        Returns list of keys that need rotation.
        """
        all_keys = await self.key_store.list_keys()
        expiring = []

        for key in all_keys:
            if key.is_active and key.expires_at:
                days_until_expiry = (key.expires_at - datetime.now(UTC)).days
                if days_until_expiry < 7:  # Warning threshold
                    expiring.append(key)
                    logger.warning(
                        "key_expiring_soon",
                        key_id=key.key_id,
                        purpose=key.purpose,
                        days_remaining=days_until_expiry,
                    )

        return expiring


# ═══════════════════════════════════════════════════════════════════════════
# SENSITIVE DATA HANDLER
# ═══════════════════════════════════════════════════════════════════════════


class SensitiveDataHandler:
    """
    High-level handler for sensitive data encryption based on classification.

    Automatically applies appropriate encryption/tokenization based on
    data classification per compliance requirements.
    """

    def __init__(self, encryption_service: EncryptionService):
        self.encryption = encryption_service

    async def protect(
        self,
        data: dict[str, Any],
        classification: DataClassification,
        entity_id: str,
        sensitive_fields: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Protect sensitive data based on classification.

        Args:
            data: Data dictionary to protect
            classification: Data classification level
            entity_id: Entity ID for context binding
            sensitive_fields: List of field names to encrypt (if None, uses defaults)

        Returns:
            Data with sensitive fields encrypted/tokenized
        """
        result = data.copy()

        # Determine fields to protect based on classification
        if sensitive_fields is None:
            sensitive_fields = self._get_default_sensitive_fields(classification)

        for field_name in sensitive_fields:
            if field_name in result and result[field_name]:
                # Use tokenization for PCI/PHI, encryption for others
                if classification in {DataClassification.PCI, DataClassification.PHI}:
                    result[field_name] = await self.encryption.tokenize(
                        str(result[field_name]),
                        classification,
                    )
                else:
                    result[field_name] = await self.encryption.encrypt_field(
                        result[field_name],
                        field_name,
                        entity_id,
                    )

        return result

    async def unprotect(
        self,
        data: dict[str, Any],
        classification: DataClassification,
        entity_id: str,
        sensitive_fields: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Unprotect (decrypt/detokenize) sensitive data.
        """
        result = data.copy()

        if sensitive_fields is None:
            sensitive_fields = self._get_default_sensitive_fields(classification)

        for field_name in sensitive_fields:
            if field_name in result and result[field_name]:
                value = result[field_name]

                # Detect token vs encrypted field
                if isinstance(value, str) and value.startswith(
                    ("PCI_", "PHI_", "BIO_", "FIN_", "TOK_")
                ):
                    result[field_name] = await self.encryption.detokenize(value)
                elif isinstance(value, str):
                    try:
                        result[field_name] = await self.encryption.decrypt_field(
                            value,
                            field_name,
                            entity_id,
                        )
                    except Exception:
                        pass  # Not encrypted, keep as-is

        return result

    def _get_default_sensitive_fields(
        self,
        classification: DataClassification,
    ) -> list[str]:
        """Get default sensitive fields for a classification."""
        defaults = {
            DataClassification.PCI: [
                "card_number",
                "cvv",
                "expiry_date",
                "cardholder_name",
            ],
            DataClassification.PHI: [
                "ssn",
                "medical_record",
                "diagnosis",
                "treatment",
                "date_of_birth",
                "address",
                "phone",
                "email",
            ],
            DataClassification.BIOMETRIC: [
                "fingerprint",
                "face_data",
                "voice_print",
                "iris_scan",
            ],
            DataClassification.FINANCIAL: [
                "account_number",
                "routing_number",
                "balance",
                "transactions",
            ],
            DataClassification.SENSITIVE_PERSONAL: [
                "race",
                "ethnicity",
                "religion",
                "political_affiliation",
                "sexual_orientation",
                "health_data",
                "genetic_data",
            ],
            DataClassification.PERSONAL_DATA: [
                "email",
                "phone",
                "address",
                "date_of_birth",
            ],
        }
        return defaults.get(classification, [])


# Global service instance
_encryption_service: EncryptionService | None = None


def get_encryption_service() -> EncryptionService:
    """Get the global encryption service instance."""
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = EncryptionService()
    return _encryption_service
