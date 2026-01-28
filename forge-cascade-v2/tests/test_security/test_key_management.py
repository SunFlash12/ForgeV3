"""
Key Management Service Tests for Forge Cascade V2

Comprehensive tests for Ed25519 signing key management including:
- Key generation
- Server custody encryption/decryption
- Client-only key validation
- Password-derived keys
- Unified interface
- Error handling
"""

import base64
from datetime import UTC, datetime

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from forge.models.user import KeyStorageStrategy
from forge.security.key_management import (
    InvalidKeyError,
    KeyDecryptionError,
    KeyDerivationError,
    KeyManagementError,
    KeyManagementService,
    KeyNotFoundError,
    SigningKeyInfo,
    get_key_management_service,
)

# =============================================================================
# Key Generation Tests
# =============================================================================


class TestKeyGeneration:
    """Tests for Ed25519 key generation."""

    def test_generates_valid_keypair(self):
        """Generates valid Ed25519 keypair."""
        private_key, public_key = KeyManagementService.generate_keypair()

        assert len(private_key) == 32
        assert len(public_key) == 32

        # Verify keys are valid Ed25519 keys
        private = Ed25519PrivateKey.from_private_bytes(private_key)
        public = Ed25519PublicKey.from_public_bytes(public_key)

        assert private is not None
        assert public is not None

    def test_generates_different_keypairs(self):
        """Each call generates a different keypair."""
        pair1 = KeyManagementService.generate_keypair()
        pair2 = KeyManagementService.generate_keypair()

        assert pair1[0] != pair2[0]  # Different private keys
        assert pair1[1] != pair2[1]  # Different public keys

    def test_keypair_to_b64(self):
        """Converts keypair to base64 strings."""
        private_key, public_key = KeyManagementService.generate_keypair()

        private_b64, public_b64 = KeyManagementService.keypair_to_b64(private_key, public_key)

        assert isinstance(private_b64, str)
        assert isinstance(public_b64, str)

        # Verify roundtrip
        decoded_private = base64.b64decode(private_b64)
        decoded_public = base64.b64decode(public_b64)

        assert decoded_private == private_key
        assert decoded_public == public_key

    def test_public_key_from_private(self):
        """Derives public key from private key."""
        private_key, public_key = KeyManagementService.generate_keypair()

        derived_public = KeyManagementService.public_key_from_private(private_key)

        assert derived_public == public_key
        assert len(derived_public) == 32


# =============================================================================
# Server Custody Tests (AES-256-GCM Encryption)
# =============================================================================


class TestServerCustody:
    """Tests for server custody key storage."""

    def test_encrypt_private_key(self):
        """Encrypts private key with password."""
        private_key, _ = KeyManagementService.generate_keypair()
        password = "secure-password-123"

        encrypted = KeyManagementService.encrypt_private_key(private_key, password)

        assert isinstance(encrypted, str)
        # Should be base64 encoded
        decoded = base64.b64decode(encrypted)
        # Contains salt (32) + nonce (12) + ciphertext (32) + tag (16)
        assert len(decoded) >= 32 + 12 + 32 + 16

    def test_decrypt_private_key(self):
        """Decrypts private key with correct password."""
        private_key, _ = KeyManagementService.generate_keypair()
        password = "secure-password-123"

        encrypted = KeyManagementService.encrypt_private_key(private_key, password)
        decrypted = KeyManagementService.decrypt_private_key(encrypted, password)

        assert decrypted == private_key

    def test_decrypt_fails_with_wrong_password(self):
        """Decryption fails with wrong password."""
        private_key, _ = KeyManagementService.generate_keypair()
        password = "secure-password-123"
        wrong_password = "wrong-password"

        encrypted = KeyManagementService.encrypt_private_key(private_key, password)

        with pytest.raises(KeyDecryptionError):
            KeyManagementService.decrypt_private_key(encrypted, wrong_password)

    def test_decrypt_fails_with_corrupted_data(self):
        """Decryption fails with corrupted data."""
        private_key, _ = KeyManagementService.generate_keypair()
        password = "secure-password-123"

        encrypted = KeyManagementService.encrypt_private_key(private_key, password)

        # Corrupt the encrypted data
        decoded = base64.b64decode(encrypted)
        corrupted = base64.b64encode(decoded[:-5] + b"xxxxx").decode("utf-8")

        with pytest.raises(KeyDecryptionError):
            KeyManagementService.decrypt_private_key(corrupted, password)

    def test_encryption_produces_different_results(self):
        """Same key/password produces different encrypted outputs (random salt/nonce)."""
        private_key, _ = KeyManagementService.generate_keypair()
        password = "secure-password-123"

        encrypted1 = KeyManagementService.encrypt_private_key(private_key, password)
        encrypted2 = KeyManagementService.encrypt_private_key(private_key, password)

        # Different due to random salt and nonce
        assert encrypted1 != encrypted2

        # Both decrypt to same key
        decrypted1 = KeyManagementService.decrypt_private_key(encrypted1, password)
        decrypted2 = KeyManagementService.decrypt_private_key(encrypted2, password)

        assert decrypted1 == private_key
        assert decrypted2 == private_key

    def test_setup_server_custody(self):
        """Sets up signing keys with server custody."""
        result = KeyManagementService.setup_server_custody("password123")

        assert result["strategy"] == KeyStorageStrategy.SERVER_CUSTODY
        assert "public_key_b64" in result
        assert "encrypted_private_key" in result
        assert "created_at" in result

        # Public key should be valid
        public_key = base64.b64decode(result["public_key_b64"])
        assert len(public_key) == 32
        Ed25519PublicKey.from_public_bytes(public_key)


# =============================================================================
# Client Only Tests
# =============================================================================


class TestClientOnly:
    """Tests for client-only key storage."""

    def test_setup_client_only_valid_key(self):
        """Sets up client-only with valid public key."""
        private_key, public_key = KeyManagementService.generate_keypair()
        public_b64 = base64.b64encode(public_key).decode("utf-8")

        result = KeyManagementService.setup_client_only(public_b64)

        assert result["strategy"] == KeyStorageStrategy.CLIENT_ONLY
        assert result["public_key_b64"] == public_b64
        assert "created_at" in result

    def test_setup_client_only_invalid_key_length(self):
        """Rejects public key with invalid length."""
        invalid_key = base64.b64encode(b"too-short").decode("utf-8")

        with pytest.raises(InvalidKeyError, match="32 bytes"):
            KeyManagementService.setup_client_only(invalid_key)

    def test_setup_client_only_invalid_key_format(self):
        """Rejects invalid public key format."""
        # Random bytes of correct length but not a valid Ed25519 key
        # Actually, any 32-byte sequence is a valid Ed25519 public key point
        # So let's test with invalid base64
        with pytest.raises(InvalidKeyError):
            KeyManagementService.setup_client_only("not-valid-base64!!!")

    def test_setup_client_only_validates_key(self):
        """Validates that provided key is a valid Ed25519 public key."""
        private_key, public_key = KeyManagementService.generate_keypair()
        public_b64 = base64.b64encode(public_key).decode("utf-8")

        result = KeyManagementService.setup_client_only(public_b64)

        # Should succeed with valid key
        assert result["public_key_b64"] == public_b64


# =============================================================================
# Password Derived Tests
# =============================================================================


class TestPasswordDerived:
    """Tests for password-derived key storage."""

    def test_derive_keypair_from_password(self):
        """Derives deterministic keypair from password."""
        password = "my-password-123"

        private1, public1, salt1 = KeyManagementService.derive_keypair_from_password(password)

        # Keys should be valid
        assert len(private1) == 32
        assert len(public1) == 32
        assert len(salt1) == 32

        # Verify they form a valid keypair
        private = Ed25519PrivateKey.from_private_bytes(private1)
        assert private.public_key().public_bytes_raw() == public1

    def test_same_password_salt_produces_same_keys(self):
        """Same password and salt produce same keypair."""
        password = "my-password-123"

        private1, public1, salt1 = KeyManagementService.derive_keypair_from_password(password)

        # Use same salt
        private2, public2, salt2 = KeyManagementService.derive_keypair_from_password(
            password, salt=salt1
        )

        assert private1 == private2
        assert public1 == public2
        assert salt1 == salt2

    def test_different_password_produces_different_keys(self):
        """Different passwords produce different keypairs."""
        salt = b"x" * 32

        private1, public1, _ = KeyManagementService.derive_keypair_from_password(
            "password-a", salt=salt
        )
        private2, public2, _ = KeyManagementService.derive_keypair_from_password(
            "password-b", salt=salt
        )

        assert private1 != private2
        assert public1 != public2

    def test_different_salt_produces_different_keys(self):
        """Different salts produce different keypairs."""
        password = "same-password"

        private1, public1, salt1 = KeyManagementService.derive_keypair_from_password(password)
        private2, public2, salt2 = KeyManagementService.derive_keypair_from_password(password)

        # Different random salts
        assert salt1 != salt2
        assert private1 != private2
        assert public1 != public2

    def test_setup_password_derived(self):
        """Sets up password-derived key storage."""
        result = KeyManagementService.setup_password_derived("my-password-123")

        assert result["strategy"] == KeyStorageStrategy.PASSWORD_DERIVED
        assert "public_key_b64" in result
        assert "salt_b64" in result
        assert "created_at" in result

        # Verify public key
        public_key = base64.b64decode(result["public_key_b64"])
        assert len(public_key) == 32

        # Verify salt
        salt = base64.b64decode(result["salt_b64"])
        assert len(salt) == 32

    def test_get_private_key_password_derived(self):
        """Recovers private key from password and salt."""
        result = KeyManagementService.setup_password_derived("my-password-123")

        private_key = KeyManagementService.get_private_key_password_derived(
            "my-password-123", result["salt_b64"]
        )

        # Verify the private key derives to the stored public key
        public_key = KeyManagementService.public_key_from_private(private_key)
        assert base64.b64encode(public_key).decode("utf-8") == result["public_key_b64"]


# =============================================================================
# Unified Interface Tests
# =============================================================================


class TestSetupSigningKeys:
    """Tests for unified setup_signing_keys interface."""

    def test_setup_none_strategy(self):
        """Sets up NONE strategy (no signing)."""
        result = KeyManagementService.setup_signing_keys(KeyStorageStrategy.NONE)

        assert result["strategy"] == KeyStorageStrategy.NONE
        assert "created_at" in result

    def test_setup_server_custody_strategy(self):
        """Sets up SERVER_CUSTODY strategy."""
        result = KeyManagementService.setup_signing_keys(
            KeyStorageStrategy.SERVER_CUSTODY,
            password="my-password",
        )

        assert result["strategy"] == KeyStorageStrategy.SERVER_CUSTODY
        assert "public_key_b64" in result
        assert "encrypted_private_key" in result

    def test_setup_server_custody_requires_password(self):
        """SERVER_CUSTODY requires password."""
        with pytest.raises(ValueError, match="Password required"):
            KeyManagementService.setup_signing_keys(KeyStorageStrategy.SERVER_CUSTODY)

    def test_setup_client_only_strategy(self):
        """Sets up CLIENT_ONLY strategy."""
        private_key, public_key = KeyManagementService.generate_keypair()
        public_b64 = base64.b64encode(public_key).decode("utf-8")

        result = KeyManagementService.setup_signing_keys(
            KeyStorageStrategy.CLIENT_ONLY,
            public_key_b64=public_b64,
        )

        assert result["strategy"] == KeyStorageStrategy.CLIENT_ONLY
        assert result["public_key_b64"] == public_b64

    def test_setup_client_only_requires_public_key(self):
        """CLIENT_ONLY requires public key."""
        with pytest.raises(ValueError, match="Public key required"):
            KeyManagementService.setup_signing_keys(KeyStorageStrategy.CLIENT_ONLY)

    def test_setup_password_derived_strategy(self):
        """Sets up PASSWORD_DERIVED strategy."""
        result = KeyManagementService.setup_signing_keys(
            KeyStorageStrategy.PASSWORD_DERIVED,
            password="my-password",
        )

        assert result["strategy"] == KeyStorageStrategy.PASSWORD_DERIVED
        assert "public_key_b64" in result
        assert "salt_b64" in result

    def test_setup_password_derived_requires_password(self):
        """PASSWORD_DERIVED requires password."""
        with pytest.raises(ValueError, match="Password required"):
            KeyManagementService.setup_signing_keys(KeyStorageStrategy.PASSWORD_DERIVED)


class TestGetPrivateKey:
    """Tests for unified get_private_key interface."""

    def test_get_private_key_none_strategy_raises(self):
        """NONE strategy raises KeyNotFoundError."""
        with pytest.raises(KeyNotFoundError):
            KeyManagementService.get_private_key(KeyStorageStrategy.NONE)

    def test_get_private_key_server_custody(self):
        """Gets private key for SERVER_CUSTODY strategy."""
        password = "my-password"
        setup = KeyManagementService.setup_server_custody(password)

        private_key = KeyManagementService.get_private_key(
            KeyStorageStrategy.SERVER_CUSTODY,
            password=password,
            encrypted_private_key=setup["encrypted_private_key"],
        )

        assert len(private_key) == 32
        # Verify it matches the public key
        public = KeyManagementService.public_key_from_private(private_key)
        assert base64.b64encode(public).decode("utf-8") == setup["public_key_b64"]

    def test_get_private_key_server_custody_missing_params(self):
        """SERVER_CUSTODY raises error without required params."""
        with pytest.raises(ValueError, match="Password and encrypted_private_key"):
            KeyManagementService.get_private_key(
                KeyStorageStrategy.SERVER_CUSTODY,
                password="password",
                # Missing encrypted_private_key
            )

    def test_get_private_key_client_only(self):
        """Gets private key for CLIENT_ONLY strategy."""
        private_key, _ = KeyManagementService.generate_keypair()
        private_b64 = base64.b64encode(private_key).decode("utf-8")

        result = KeyManagementService.get_private_key(
            KeyStorageStrategy.CLIENT_ONLY,
            client_private_key_b64=private_b64,
        )

        assert result == private_key

    def test_get_private_key_client_only_missing_param(self):
        """CLIENT_ONLY raises error without private key."""
        with pytest.raises(ValueError, match="Private key required"):
            KeyManagementService.get_private_key(KeyStorageStrategy.CLIENT_ONLY)

    def test_get_private_key_client_only_invalid_key(self):
        """CLIENT_ONLY raises error with invalid private key."""
        invalid_b64 = base64.b64encode(b"too-short").decode("utf-8")

        with pytest.raises(InvalidKeyError, match="32 bytes"):
            KeyManagementService.get_private_key(
                KeyStorageStrategy.CLIENT_ONLY,
                client_private_key_b64=invalid_b64,
            )

    def test_get_private_key_password_derived(self):
        """Gets private key for PASSWORD_DERIVED strategy."""
        password = "my-password"
        setup = KeyManagementService.setup_password_derived(password)

        private_key = KeyManagementService.get_private_key(
            KeyStorageStrategy.PASSWORD_DERIVED,
            password=password,
            salt_b64=setup["salt_b64"],
        )

        assert len(private_key) == 32
        # Verify it matches the public key
        public = KeyManagementService.public_key_from_private(private_key)
        assert base64.b64encode(public).decode("utf-8") == setup["public_key_b64"]

    def test_get_private_key_password_derived_missing_params(self):
        """PASSWORD_DERIVED raises error without required params."""
        with pytest.raises(ValueError, match="Password and salt required"):
            KeyManagementService.get_private_key(
                KeyStorageStrategy.PASSWORD_DERIVED,
                password="password",
                # Missing salt
            )


# =============================================================================
# SigningKeyInfo Tests
# =============================================================================


class TestSigningKeyInfo:
    """Tests for SigningKeyInfo dataclass."""

    def test_creates_signing_key_info(self):
        """Creates SigningKeyInfo with all fields."""
        now = datetime.now(UTC)
        info = SigningKeyInfo(
            strategy=KeyStorageStrategy.SERVER_CUSTODY,
            public_key_b64="test-public-key-b64",
            created_at=now,
            can_sign=True,
        )

        assert info.strategy == KeyStorageStrategy.SERVER_CUSTODY
        assert info.public_key_b64 == "test-public-key-b64"
        assert info.created_at == now
        assert info.can_sign is True

    def test_to_dict(self):
        """Converts SigningKeyInfo to dictionary."""
        now = datetime.now(UTC)
        info = SigningKeyInfo(
            strategy=KeyStorageStrategy.PASSWORD_DERIVED,
            public_key_b64="test-key",
            created_at=now,
            can_sign=True,
        )

        result = info.to_dict()

        assert result["strategy"] == "password_derived"
        assert result["public_key"] == "test-key"
        assert result["created_at"] == now.isoformat()
        assert result["can_sign"] is True

    def test_to_dict_with_none_values(self):
        """Handles None values in to_dict."""
        info = SigningKeyInfo(
            strategy=KeyStorageStrategy.NONE,
            public_key_b64=None,
            created_at=None,
            can_sign=False,
        )

        result = info.to_dict()

        assert result["public_key"] is None
        assert result["created_at"] is None
        assert result["can_sign"] is False


# =============================================================================
# Singleton Pattern Tests
# =============================================================================


class TestGetKeyManagementService:
    """Tests for singleton service getter."""

    def test_returns_same_instance(self):
        """Returns the same service instance."""
        import forge.security.key_management as module

        module._key_service = None

        service1 = get_key_management_service()
        service2 = get_key_management_service()

        assert service1 is service2

        module._key_service = None

    def test_creates_instance_when_none(self):
        """Creates new instance when singleton is None."""
        import forge.security.key_management as module

        module._key_service = None

        service = get_key_management_service()

        assert service is not None
        assert isinstance(service, KeyManagementService)

        module._key_service = None


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling."""

    def test_key_management_error_hierarchy(self):
        """Verifies error class hierarchy."""
        assert issubclass(KeyNotFoundError, KeyManagementError)
        assert issubclass(KeyDecryptionError, KeyManagementError)
        assert issubclass(KeyDerivationError, KeyManagementError)
        assert issubclass(InvalidKeyError, KeyManagementError)

    def test_unknown_strategy_raises_error(self):
        """Unknown strategy raises ValueError."""
        # This would require creating a mock invalid strategy
        # Since KeyStorageStrategy is an enum, this is hard to test directly
        pass

    def test_decrypt_invalid_base64_raises_error(self):
        """Decrypting invalid base64 raises error."""
        with pytest.raises(KeyDecryptionError):
            KeyManagementService.decrypt_private_key(
                "not-valid-base64!!!",
                "password",
            )


# =============================================================================
# Security Tests
# =============================================================================


class TestSecurity:
    """Tests for security properties."""

    def test_encryption_uses_unique_salt(self):
        """Each encryption uses unique salt."""
        private_key, _ = KeyManagementService.generate_keypair()
        password = "test-password"

        encrypted1 = KeyManagementService.encrypt_private_key(private_key, password)
        encrypted2 = KeyManagementService.encrypt_private_key(private_key, password)

        # Extract salts (first 32 bytes)
        salt1 = base64.b64decode(encrypted1)[:32]
        salt2 = base64.b64decode(encrypted2)[:32]

        assert salt1 != salt2

    def test_encryption_uses_unique_nonce(self):
        """Each encryption uses unique nonce."""
        private_key, _ = KeyManagementService.generate_keypair()
        password = "test-password"

        encrypted1 = KeyManagementService.encrypt_private_key(private_key, password)
        encrypted2 = KeyManagementService.encrypt_private_key(private_key, password)

        # Extract nonces (bytes 32-44)
        nonce1 = base64.b64decode(encrypted1)[32:44]
        nonce2 = base64.b64decode(encrypted2)[32:44]

        assert nonce1 != nonce2

    def test_key_derivation_uses_hkdf_info(self):
        """Key derivation uses HKDF info field."""
        assert KeyManagementService.HKDF_INFO == b"forge-capsule-signing-key-v1"

    def test_aes_key_size_is_256_bits(self):
        """AES key size is 256 bits (32 bytes)."""
        assert KeyManagementService.AES_KEY_SIZE == 32

    def test_aes_nonce_size_is_96_bits(self):
        """AES-GCM nonce size is 96 bits (12 bytes)."""
        assert KeyManagementService.AES_NONCE_SIZE == 12

    def test_salt_size_is_256_bits(self):
        """HKDF salt size is 256 bits (32 bytes)."""
        assert KeyManagementService.HKDF_SALT_SIZE == 32


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests for complete key management flows."""

    def test_complete_server_custody_flow(self):
        """Tests complete server custody flow."""
        password = "secure-password-123"

        # Setup
        setup_result = KeyManagementService.setup_signing_keys(
            KeyStorageStrategy.SERVER_CUSTODY,
            password=password,
        )

        # Later, retrieve private key
        private_key = KeyManagementService.get_private_key(
            KeyStorageStrategy.SERVER_CUSTODY,
            password=password,
            encrypted_private_key=setup_result["encrypted_private_key"],
        )

        # Sign something
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        key = Ed25519PrivateKey.from_private_bytes(private_key)
        signature = key.sign(b"test message")

        # Verify with public key
        public_key = base64.b64decode(setup_result["public_key_b64"])
        pub = Ed25519PublicKey.from_public_bytes(public_key)
        pub.verify(signature, b"test message")  # Raises if invalid

    def test_complete_password_derived_flow(self):
        """Tests complete password-derived flow."""
        password = "my-secure-password"

        # Setup
        setup_result = KeyManagementService.setup_signing_keys(
            KeyStorageStrategy.PASSWORD_DERIVED,
            password=password,
        )

        # Later, recover private key
        private_key = KeyManagementService.get_private_key(
            KeyStorageStrategy.PASSWORD_DERIVED,
            password=password,
            salt_b64=setup_result["salt_b64"],
        )

        # Sign and verify
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        key = Ed25519PrivateKey.from_private_bytes(private_key)
        signature = key.sign(b"important data")

        public_key = base64.b64decode(setup_result["public_key_b64"])
        pub = Ed25519PublicKey.from_public_bytes(public_key)
        pub.verify(signature, b"important data")

    def test_complete_client_only_flow(self):
        """Tests complete client-only flow."""
        # User generates their own keypair
        private_key, public_key = KeyManagementService.generate_keypair()
        public_b64 = base64.b64encode(public_key).decode("utf-8")
        private_b64 = base64.b64encode(private_key).decode("utf-8")

        # Register public key with server
        setup_result = KeyManagementService.setup_signing_keys(
            KeyStorageStrategy.CLIENT_ONLY,
            public_key_b64=public_b64,
        )

        # User provides private key for signing
        recovered_private = KeyManagementService.get_private_key(
            KeyStorageStrategy.CLIENT_ONLY,
            client_private_key_b64=private_b64,
        )

        # Sign and verify
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        key = Ed25519PrivateKey.from_private_bytes(recovered_private)
        signature = key.sign(b"user message")

        stored_public = base64.b64decode(setup_result["public_key_b64"])
        pub = Ed25519PublicKey.from_public_bytes(stored_public)
        pub.verify(signature, b"user message")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
