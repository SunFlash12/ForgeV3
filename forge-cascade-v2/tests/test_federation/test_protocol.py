"""
Tests for federation protocol.
"""

import base64
import hashlib
import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from forge.federation.models import (
    FederatedPeer,
    PeerHandshake,
)
from forge.federation.protocol import (
    CertificatePinStore,
    DNSPinStore,
    DNSRebindingError,
    FederationProtocol,
    NonceStore,
    PinnedCertificate,
    PinnedConnection,
    ReplayAttackError,
    SSRFError,
    _compute_cert_fingerprint,
    get_dns_pin_store,
    get_nonce_store,
    validate_url_for_ssrf,
)


class TestSSRFError:
    """Tests for SSRFError exception."""

    def test_ssrf_error_creation(self):
        """Test creating SSRF error."""
        error = SSRFError("Blocked private IP")
        assert str(error) == "Blocked private IP"


class TestDNSRebindingError:
    """Tests for DNSRebindingError exception."""

    def test_dns_rebinding_error_creation(self):
        """Test creating DNS rebinding error."""
        error = DNSRebindingError("IP changed")
        assert str(error) == "IP changed"


class TestReplayAttackError:
    """Tests for ReplayAttackError exception."""

    def test_replay_attack_error_creation(self):
        """Test creating replay attack error."""
        error = ReplayAttackError("Nonce reused")
        assert str(error) == "Nonce reused"


class TestPinnedConnection:
    """Tests for PinnedConnection dataclass."""

    def test_create_pinned_connection(self):
        """Test creating pinned connection."""
        now = datetime.now(UTC)
        pin = PinnedConnection(
            hostname="example.com",
            pinned_ips=["1.2.3.4", "5.6.7.8"],
            pinned_at=now,
            port=443,
            ttl_seconds=300,
        )
        assert pin.hostname == "example.com"
        assert len(pin.pinned_ips) == 2
        assert pin.port == 443
        assert pin.ttl_seconds == 300

    def test_is_expired_fresh(self):
        """Test fresh pin is not expired."""
        pin = PinnedConnection(
            hostname="example.com",
            pinned_ips=["1.2.3.4"],
            pinned_at=datetime.now(UTC),
            ttl_seconds=300,
        )
        assert pin.is_expired() is False

    def test_is_expired_old(self):
        """Test old pin is expired."""
        pin = PinnedConnection(
            hostname="example.com",
            pinned_ips=["1.2.3.4"],
            pinned_at=datetime.now(UTC) - timedelta(seconds=301),
            ttl_seconds=300,
        )
        assert pin.is_expired() is True


class TestPinnedCertificate:
    """Tests for PinnedCertificate dataclass."""

    def test_create_pinned_certificate(self):
        """Test creating pinned certificate."""
        now = datetime.now(UTC)
        pin = PinnedCertificate(
            peer_id="peer-123",
            hostname="example.com",
            fingerprint_sha256="abc123def456",
            pinned_at=now,
            last_verified=now,
            pin_type="tofu",
        )
        assert pin.peer_id == "peer-123"
        assert pin.fingerprint_sha256 == "abc123def456"
        assert pin.pin_type == "tofu"

    def test_certificate_rotation(self):
        """Test certificate with rotation scheduled."""
        now = datetime.now(UTC)
        pin = PinnedCertificate(
            peer_id="peer-123",
            hostname="example.com",
            fingerprint_sha256="current123",
            pinned_at=now,
            last_verified=now,
            pin_type="explicit",
            next_fingerprint="next456",
            next_valid_from=now + timedelta(days=7),
        )
        assert pin.next_fingerprint == "next456"
        assert pin.next_valid_from is not None


class TestDNSPinStore:
    """Tests for DNSPinStore."""

    def test_pin_hostname(self):
        """Test pinning a hostname."""
        store = DNSPinStore()
        pin = store.pin_hostname("example.com", 443, ["1.2.3.4", "5.6.7.8"])
        assert pin.hostname == "example.com"
        assert len(pin.pinned_ips) == 2

    def test_get_pinned_ips(self):
        """Test getting pinned IPs."""
        store = DNSPinStore()
        store.pin_hostname("example.com", 443, ["1.2.3.4"])

        ips = store.get_pinned_ips("example.com", 443)
        assert ips == ["1.2.3.4"]

    def test_get_pinned_ips_not_found(self):
        """Test getting IPs for unknown hostname."""
        store = DNSPinStore()
        ips = store.get_pinned_ips("unknown.com", 443)
        assert ips is None

    def test_get_pinned_ips_expired(self):
        """Test getting expired pinned IPs."""
        store = DNSPinStore(ttl_seconds=0)  # Immediate expiration
        store.pin_hostname("example.com", 443, ["1.2.3.4"])

        # Wait for expiration
        import time

        time.sleep(0.01)

        ips = store.get_pinned_ips("example.com", 443)
        assert ips is None

    def test_verify_ip_matching(self):
        """Test verifying matching IP."""
        store = DNSPinStore()
        store.pin_hostname("example.com", 443, ["1.2.3.4", "5.6.7.8"])

        assert store.verify_ip("example.com", 443, "1.2.3.4") is True
        assert store.verify_ip("example.com", 443, "5.6.7.8") is True

    def test_verify_ip_not_matching(self):
        """Test verifying non-matching IP."""
        store = DNSPinStore()
        store.pin_hostname("example.com", 443, ["1.2.3.4"])

        assert store.verify_ip("example.com", 443, "9.9.9.9") is False

    def test_verify_ip_no_pin(self):
        """Test verifying IP when no pin exists."""
        store = DNSPinStore()
        assert store.verify_ip("unknown.com", 443, "1.2.3.4") is True

    def test_clear_pin(self):
        """Test clearing a pin."""
        store = DNSPinStore()
        store.pin_hostname("example.com", 443, ["1.2.3.4"])
        assert store.get_pinned_ips("example.com", 443) is not None

        store.clear_pin("example.com", 443)
        assert store.get_pinned_ips("example.com", 443) is None

    def test_max_pins_eviction(self):
        """Test eviction when max pins reached."""
        store = DNSPinStore()
        store.MAX_PINS = 10  # Set low limit for testing

        # Fill up the store
        for i in range(15):
            store.pin_hostname(f"host{i}.com", 443, [f"1.2.3.{i}"])

        # Should have evicted oldest entries
        assert len(store._pins) <= 10


class TestCertificatePinStore:
    """Tests for CertificatePinStore."""

    def test_pin_certificate_tofu(self):
        """Test pinning certificate with TOFU."""
        store = CertificatePinStore()
        pin = store.pin_certificate(
            peer_id="peer-123",
            hostname="example.com",
            fingerprint="ABCDEF123456",
            pin_type="tofu",
        )
        assert pin.peer_id == "peer-123"
        assert pin.fingerprint_sha256 == "abcdef123456"  # Lowercased
        assert pin.pin_type == "tofu"

    def test_pin_certificate_explicit(self):
        """Test pinning certificate explicitly."""
        store = CertificatePinStore()
        pin = store.pin_certificate(
            peer_id="peer-123",
            hostname="example.com",
            fingerprint="ABC123",
            pin_type="explicit",
        )
        assert pin.pin_type == "explicit"

    def test_tofu_cannot_overwrite_explicit(self):
        """Test TOFU cannot overwrite explicit pin."""
        store = CertificatePinStore()

        # First, pin explicitly
        store.pin_certificate("peer-123", "example.com", "explicit123", "explicit")

        # Try to overwrite with TOFU
        pin = store.pin_certificate("peer-123", "example.com", "tofu456", "tofu")

        # Should return existing explicit pin
        assert pin.fingerprint_sha256 == "explicit123"

    def test_get_pin(self):
        """Test getting pinned certificate."""
        store = CertificatePinStore()
        store.pin_certificate("peer-123", "example.com", "abc123")

        pin = store.get_pin("peer-123")
        assert pin is not None
        assert pin.fingerprint_sha256 == "abc123"

    def test_get_pin_not_found(self):
        """Test getting non-existent pin."""
        store = CertificatePinStore()
        pin = store.get_pin("unknown-peer")
        assert pin is None

    def test_verify_certificate_match(self):
        """Test verifying matching certificate."""
        store = CertificatePinStore()
        store.pin_certificate("peer-123", "example.com", "abc123")

        result = store.verify_certificate("peer-123", "ABC123", "example.com")
        assert result is True

    def test_verify_certificate_no_pin(self):
        """Test verifying when no pin exists (TOFU allowed)."""
        store = CertificatePinStore()
        result = store.verify_certificate("peer-123", "abc123", "example.com")
        assert result is True

    def test_verify_certificate_mismatch(self):
        """Test verifying mismatched certificate."""
        store = CertificatePinStore()
        store.pin_certificate("peer-123", "example.com", "expected123")

        result = store.verify_certificate("peer-123", "different456", "example.com")
        assert result is False

    def test_verify_certificate_rotation(self):
        """Test certificate rotation verification."""
        store = CertificatePinStore()
        store.pin_certificate("peer-123", "example.com", "current123")

        # Announce rotation
        store.announce_rotation("peer-123", "next456", datetime.now(UTC) - timedelta(hours=1))

        # Verify with new cert
        result = store.verify_certificate("peer-123", "next456", "example.com")
        assert result is True

    def test_announce_rotation(self):
        """Test announcing certificate rotation."""
        store = CertificatePinStore()
        store.pin_certificate("peer-123", "example.com", "current123")

        future = datetime.now(UTC) + timedelta(days=7)
        result = store.announce_rotation("peer-123", "next456", future)

        assert result is True
        pin = store.get_pin("peer-123")
        assert pin.next_fingerprint == "next456"
        assert pin.next_valid_from == future

    def test_announce_rotation_unknown_peer(self):
        """Test announcing rotation for unknown peer."""
        store = CertificatePinStore()
        result = store.announce_rotation("unknown", "next456", datetime.now(UTC))
        assert result is False

    def test_remove_pin(self):
        """Test removing certificate pin."""
        store = CertificatePinStore()
        store.pin_certificate("peer-123", "example.com", "abc123")
        assert store.get_pin("peer-123") is not None

        store.remove_pin("peer-123")
        assert store.get_pin("peer-123") is None


class TestNonceStore:
    """Tests for NonceStore."""

    def test_generate_nonce(self):
        """Test generating nonce."""
        store = NonceStore()
        nonce = store.generate_nonce()

        assert len(nonce) == 32
        assert all(c in "0123456789abcdef" for c in nonce)

    def test_generate_unique_nonces(self):
        """Test nonces are unique."""
        store = NonceStore()
        nonces = [store.generate_nonce() for _ in range(100)]
        assert len(set(nonces)) == 100

    def test_mark_used_new_nonce(self):
        """Test marking new nonce as used."""
        store = NonceStore()
        nonce = store.generate_nonce()

        result = store.mark_used(nonce)
        assert result is True

    def test_mark_used_duplicate_nonce(self):
        """Test marking duplicate nonce (replay attack)."""
        store = NonceStore()
        nonce = store.generate_nonce()

        store.mark_used(nonce)
        result = store.mark_used(nonce)
        assert result is False

    def test_is_valid_and_unused(self):
        """Test checking if nonce is valid and unused."""
        store = NonceStore()
        nonce = store.generate_nonce()

        assert store.is_valid_and_unused(nonce) is True
        store.mark_used(nonce)
        assert store.is_valid_and_unused(nonce) is False

    def test_is_valid_invalid_format(self):
        """Test checking nonce with invalid format."""
        store = NonceStore()

        # Too short
        assert store.is_valid_and_unused("abc123") is False

        # Too long
        assert store.is_valid_and_unused("a" * 64) is False

        # Invalid characters
        assert store.is_valid_and_unused("ghij" + "a" * 28) is False

        # Empty
        assert store.is_valid_and_unused("") is False

        # None
        assert store.is_valid_and_unused(None) is False

    def test_stats(self):
        """Test getting nonce store stats."""
        store = NonceStore()
        for _ in range(10):
            store.mark_used(store.generate_nonce())

        stats = store.stats()
        assert stats["total_nonces"] == 10
        assert "max_nonces" in stats
        assert "ttl_seconds" in stats
        assert "utilization_pct" in stats

    def test_max_nonces_eviction(self):
        """Test eviction when max nonces reached."""
        store = NonceStore(max_nonces=10)

        for _ in range(15):
            nonce = store.generate_nonce()
            store.mark_used(nonce)

        # Should have evicted some entries
        assert store.stats()["total_nonces"] <= 10


class TestValidateURLForSSRF:
    """Tests for validate_url_for_ssrf function."""

    @patch("forge.federation.protocol.get_settings")
    @patch("forge.federation.protocol.socket.getaddrinfo")
    def test_valid_public_url(self, mock_getaddrinfo, mock_settings):
        """Test validating public URL."""
        mock_settings.return_value.app_env = "development"
        mock_getaddrinfo.return_value = [
            (2, 1, 6, "", ("93.184.216.34", 443)),
        ]

        result = validate_url_for_ssrf("https://example.com/api", allow_private=False)

        assert result.url == "https://example.com/api"
        assert result.hostname == "example.com"
        assert result.port == 443
        assert "93.184.216.34" in result.pinned_ips

    @patch("forge.federation.protocol.get_settings")
    def test_blocked_localhost(self, mock_settings):
        """Test blocking localhost."""
        mock_settings.return_value.app_env = "development"

        with pytest.raises(SSRFError, match="Blocked hostname"):
            validate_url_for_ssrf("http://localhost/api", allow_private=False)

    @patch("forge.federation.protocol.get_settings")
    def test_blocked_127_0_0_1(self, mock_settings):
        """Test blocking 127.0.0.1."""
        mock_settings.return_value.app_env = "development"

        with pytest.raises(SSRFError, match="Blocked hostname"):
            validate_url_for_ssrf("http://127.0.0.1/api", allow_private=False)

    @patch("forge.federation.protocol.get_settings")
    def test_blocked_metadata_endpoint(self, mock_settings):
        """Test blocking cloud metadata endpoints."""
        mock_settings.return_value.app_env = "development"

        with pytest.raises(SSRFError, match="Blocked hostname"):
            validate_url_for_ssrf("http://169.254.169.254/latest/meta-data", allow_private=False)

    @patch("forge.federation.protocol.get_settings")
    def test_invalid_scheme(self, mock_settings):
        """Test blocking invalid scheme."""
        mock_settings.return_value.app_env = "development"

        with pytest.raises(SSRFError, match="Invalid URL scheme"):
            validate_url_for_ssrf("ftp://example.com/file", allow_private=False)

    @patch("forge.federation.protocol.get_settings")
    def test_https_required_production(self, mock_settings):
        """Test HTTPS required in production."""
        mock_settings.return_value.app_env = "production"

        with pytest.raises(SSRFError, match="HTTPS required"):
            validate_url_for_ssrf("http://example.com/api", allow_private=False)

    @patch("forge.federation.protocol.get_settings")
    @patch("forge.federation.protocol.socket.getaddrinfo")
    def test_blocked_private_ip(self, mock_getaddrinfo, mock_settings):
        """Test blocking private IP resolution."""
        mock_settings.return_value.app_env = "development"
        mock_getaddrinfo.return_value = [
            (2, 1, 6, "", ("192.168.1.1", 443)),
        ]

        with pytest.raises(SSRFError, match="Private IP"):
            validate_url_for_ssrf("https://internal.corp/api", allow_private=False)

    @patch("forge.federation.protocol.get_settings")
    @patch("forge.federation.protocol.socket.getaddrinfo")
    def test_allow_private_development(self, mock_getaddrinfo, mock_settings):
        """Test allowing private IPs in development."""
        mock_settings.return_value.app_env = "development"
        mock_getaddrinfo.return_value = [
            (2, 1, 6, "", ("192.168.1.1", 443)),
        ]

        result = validate_url_for_ssrf("https://internal.corp/api", allow_private=True)
        assert result.hostname == "internal.corp"


class TestComputeCertFingerprint:
    """Tests for _compute_cert_fingerprint function."""

    def test_compute_fingerprint(self):
        """Test computing certificate fingerprint."""
        cert_der = b"fake certificate data"
        fingerprint = _compute_cert_fingerprint(cert_der)

        expected = hashlib.sha256(cert_der).hexdigest()
        assert fingerprint == expected


class TestFederationProtocol:
    """Tests for FederationProtocol class."""

    @pytest.fixture
    def protocol(self):
        """Create protocol instance."""
        return FederationProtocol(
            instance_id="test-instance",
            instance_name="Test Instance",
            key_storage_path="/tmp/test_keys",
        )

    @pytest.mark.asyncio
    async def test_initialize(self, protocol):
        """Test protocol initialization."""
        with patch.object(protocol, "_load_or_generate_keys", new_callable=AsyncMock):
            await protocol.initialize()

            assert protocol._http_client is not None
            await protocol.shutdown()

    @pytest.mark.asyncio
    async def test_shutdown(self, protocol):
        """Test protocol shutdown."""
        with patch.object(protocol, "_load_or_generate_keys", new_callable=AsyncMock):
            await protocol.initialize()
            await protocol.shutdown()
            # Should not raise

    def test_get_public_key_not_initialized(self, protocol):
        """Test getting public key before initialization."""
        assert protocol.get_public_key() == ""

    @pytest.mark.asyncio
    async def test_sign_message_not_initialized(self, protocol):
        """Test signing message before initialization."""
        with pytest.raises(RuntimeError, match="Protocol not initialized"):
            protocol.sign_message(b"test message")

    @pytest.mark.asyncio
    async def test_create_handshake(self, protocol):
        """Test creating handshake."""
        # Mock key generation
        from cryptography.hazmat.primitives.asymmetric import ed25519

        protocol._private_key = ed25519.Ed25519PrivateKey.generate()
        protocol._public_key = protocol._private_key.public_key()
        protocol._public_key_b64 = base64.b64encode(
            protocol._public_key.public_bytes(
                encoding=__import__(
                    "cryptography.hazmat.primitives.serialization", fromlist=["Encoding"]
                ).Encoding.Raw,
                format=__import__(
                    "cryptography.hazmat.primitives.serialization", fromlist=["PublicFormat"]
                ).PublicFormat.Raw,
            )
        ).decode()

        handshake = await protocol.create_handshake()

        assert handshake.instance_id == "test-instance"
        assert handshake.instance_name == "Test Instance"
        assert handshake.api_version == "1.0"
        assert handshake.public_key == protocol._public_key_b64
        assert handshake.nonce is not None
        assert len(handshake.nonce) == 32

    @pytest.mark.asyncio
    async def test_verify_handshake_valid(self, protocol):
        """Test verifying valid handshake."""
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ed25519

        # Generate keys
        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        public_key_b64 = base64.b64encode(
            public_key.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            )
        ).decode()

        # Create handshake data
        now = datetime.now(UTC)
        nonce = protocol._nonce_store.generate_nonce()

        handshake_data = {
            "instance_id": "remote-instance",
            "instance_name": "Remote Instance",
            "api_version": "1.0",
            "public_key": public_key_b64,
            "timestamp": now.isoformat(),
            "nonce": nonce,
        }

        message = json.dumps(handshake_data, sort_keys=True).encode()
        signature = base64.b64encode(private_key.sign(message)).decode()

        handshake = PeerHandshake(
            instance_id="remote-instance",
            instance_name="Remote Instance",
            api_version="1.0",
            public_key=public_key_b64,
            signature=signature,
            timestamp=now,
            nonce=nonce,
        )

        result = protocol.verify_handshake(handshake)
        assert result is True

    @pytest.mark.asyncio
    async def test_verify_handshake_no_nonce(self, protocol):
        """Test rejecting handshake without nonce."""
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ed25519

        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        public_key_b64 = base64.b64encode(
            public_key.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            )
        ).decode()

        now = datetime.now(UTC)
        handshake_data = {
            "instance_id": "remote",
            "instance_name": "Remote",
            "api_version": "1.0",
            "public_key": public_key_b64,
            "timestamp": now.isoformat(),
        }

        message = json.dumps(handshake_data, sort_keys=True).encode()
        signature = base64.b64encode(private_key.sign(message)).decode()

        handshake = PeerHandshake(
            instance_id="remote",
            instance_name="Remote",
            api_version="1.0",
            public_key=public_key_b64,
            signature=signature,
            timestamp=now,
            nonce=None,  # No nonce
        )

        result = protocol.verify_handshake(handshake)
        assert result is False

    @pytest.mark.asyncio
    async def test_verify_handshake_old_timestamp(self, protocol):
        """Test rejecting handshake with old timestamp."""
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ed25519

        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        public_key_b64 = base64.b64encode(
            public_key.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            )
        ).decode()

        old_time = datetime.now(UTC) - timedelta(minutes=10)  # Too old
        nonce = protocol._nonce_store.generate_nonce()

        handshake = PeerHandshake(
            instance_id="remote",
            instance_name="Remote",
            api_version="1.0",
            public_key=public_key_b64,
            signature="fake",
            timestamp=old_time,
            nonce=nonce,
        )

        result = protocol.verify_handshake(handshake)
        assert result is False

    def test_verify_signature_valid(self, protocol):
        """Test verifying valid signature."""
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ed25519

        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        public_key_b64 = base64.b64encode(
            public_key.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            )
        ).decode()

        message = b"test message"
        signature = base64.b64encode(private_key.sign(message)).decode()

        result = protocol.verify_signature(message, signature, public_key_b64)
        assert result is True

    def test_verify_signature_invalid(self, protocol):
        """Test verifying invalid signature."""
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ed25519

        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        public_key_b64 = base64.b64encode(
            public_key.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            )
        ).decode()

        message = b"test message"
        wrong_signature = base64.b64encode(b"wrong signature" + b"\x00" * 50).decode()

        result = protocol.verify_signature(message, wrong_signature, public_key_b64)
        assert result is False

    def test_compute_content_hash(self, protocol):
        """Test computing content hash."""
        content = {"key": "value", "list": [1, 2, 3]}
        hash1 = protocol.compute_content_hash(content)
        hash2 = protocol.compute_content_hash(content)

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex

    def test_compute_content_hash_different_content(self, protocol):
        """Test content hash differs for different content."""
        hash1 = protocol.compute_content_hash({"key": "value1"})
        hash2 = protocol.compute_content_hash({"key": "value2"})

        assert hash1 != hash2

    @pytest.mark.asyncio
    async def test_check_peer_health_not_initialized(self, protocol):
        """Test checking peer health before initialization."""
        peer = FederatedPeer(
            name="Test",
            url="https://peer.example.com",
            public_key="key==",
        )

        with pytest.raises(RuntimeError, match="Protocol not initialized"):
            await protocol.check_peer_health(peer)


class TestGlobalStores:
    """Tests for global store functions."""

    def test_get_nonce_store(self):
        """Test getting global nonce store."""
        store = get_nonce_store()
        assert isinstance(store, NonceStore)

        # Should return same instance
        store2 = get_nonce_store()
        assert store is store2

    def test_get_dns_pin_store(self):
        """Test getting global DNS pin store."""
        store = get_dns_pin_store()
        assert isinstance(store, DNSPinStore)
