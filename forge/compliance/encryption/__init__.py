"""
Forge Compliance Framework - Encryption Module

Provides encryption services for data protection per:
- SOC 2 CC6.1
- ISO 27001 A.8.24
- NIST SC-8/SC-28
- PCI-DSS 3.5
- HIPAA 164.312
"""

from forge.compliance.encryption.service import (
    EncryptionKey,
    EncryptedData,
    KeyStore,
    InMemoryKeyStore,
    EncryptionService,
    SensitiveDataHandler,
    get_encryption_service,
)

__all__ = [
    "EncryptionKey",
    "EncryptedData",
    "KeyStore",
    "InMemoryKeyStore",
    "EncryptionService",
    "SensitiveDataHandler",
    "get_encryption_service",
]
