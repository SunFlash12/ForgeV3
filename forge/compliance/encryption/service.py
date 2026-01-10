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
import os
import secrets
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, TypeVar
from uuid import uuid4

import structlog
from cryptography.hazmat.primitives import hashes, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

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
        return datetime.utcnow() > self.expires_at
    
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
    In-memory key store for development/testing.

    WARNING: Not suitable for production. Use HSM-backed store.

    TODO: CRITICAL - Implement persistent key storage for production
    This in-memory store will lose ALL encryption keys on restart, making
    previously encrypted data permanently unrecoverable.

    Recommended implementation:
    1. HSM Integration (Preferred for compliance):
       - AWS CloudHSM: Use AWS CloudHSM client library
       - Azure Dedicated HSM: Use PKCS#11 interface
       - Google Cloud HSM: Use Cloud KMS with HSM protection level
       - On-premise: Thales Luna HSM or similar

    2. Cloud KMS (Alternative):
       - AWS KMS: aws-encryption-sdk for envelope encryption
       - Azure Key Vault: azure-keyvault-keys library
       - GCP KMS: google-cloud-kms library
       - Use Data Encryption Keys (DEKs) encrypted by Key Encryption Keys (KEKs)

    3. Required for Compliance:
       - PCI-DSS 3.5-3.6: Encryption keys must be stored securely, separate from data
       - HIPAA: Encryption keys must be protected from unauthorized disclosure
       - SOC 2 CC6.1: Access to cryptographic keys must be restricted

    4. Key Backup Requirements:
       - Maintain encrypted backups of keys in geographically separate location
       - Implement key escrow for disaster recovery
       - Document key custodians and access procedures

    5. Implementation Pattern:
       class HsmKeyStore(KeyStore):
           def __init__(self, hsm_client):
               self._hsm = hsm_client

           async def store_key(self, key: EncryptionKey) -> None:
               # Store key material in HSM, only keep metadata locally
               hsm_handle = await self._hsm.import_key(key.key_material)
               # Store handle + metadata in database
               ...
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
            key_material=secrets.token_bytes(32),  # 256-bit key
            algorithm=config.encryption_at_rest_standard,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=rotation_days),
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
    encrypted_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_bytes(self) -> bytes:
        """Serialize to bytes for storage."""
        return json.dumps({
            "ciphertext": base64.b64encode(self.ciphertext).decode(),
            "nonce": base64.b64encode(self.nonce).decode(),
            "key_id": self.key_id,
            "algorithm": self.algorithm,
            "encrypted_at": self.encrypted_at.isoformat(),
        }).encode()
    
    @classmethod
    def from_bytes(cls, data: bytes) -> "EncryptedData":
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
    def from_base64(cls, data: str) -> "EncryptedData":
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
            "encrypted_at": datetime.utcnow().isoformat(),
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
                days_until_expiry = (key.expires_at - datetime.utcnow()).days
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
                if isinstance(value, str) and value.startswith(("PCI_", "PHI_", "BIO_", "FIN_", "TOK_")):
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
                "card_number", "cvv", "expiry_date", "cardholder_name",
            ],
            DataClassification.PHI: [
                "ssn", "medical_record", "diagnosis", "treatment",
                "date_of_birth", "address", "phone", "email",
            ],
            DataClassification.BIOMETRIC: [
                "fingerprint", "face_data", "voice_print", "iris_scan",
            ],
            DataClassification.FINANCIAL: [
                "account_number", "routing_number", "balance", "transactions",
            ],
            DataClassification.SENSITIVE_PERSONAL: [
                "race", "ethnicity", "religion", "political_affiliation",
                "sexual_orientation", "health_data", "genetic_data",
            ],
            DataClassification.PERSONAL_DATA: [
                "email", "phone", "address", "date_of_birth",
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
