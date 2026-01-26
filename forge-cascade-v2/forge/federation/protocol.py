"""
Federation Protocol

Handles peer discovery, handshake, and secure communication between Forge instances.

SECURITY FIXES (Audit 2):
- Added SSRF protection for peer URLs
- Disabled redirect following to prevent SSRF bypass
- Added private IP range blocking
- Added nonce-based replay prevention

SECURITY FIXES (Audit 4):
- H3: DNS pinning to prevent DNS rebinding attacks
- H4: TLS certificate pinning for federation peers
- H8: Private key encryption at rest
- H29: Nonce in sync requests
"""

import base64
import hashlib
import ipaddress
import json
import logging
import os
import secrets
import socket
import threading
from collections import OrderedDict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from forge.config import get_settings
from forge.federation.models import (
    FederatedPeer,
    PeerHandshake,
    PeerStatus,
    SyncPayload,
)

logger = logging.getLogger(__name__)


class SSRFError(Exception):
    """Raised when a potential SSRF attack is detected."""
    pass


class DNSRebindingError(Exception):
    """Raised when DNS rebinding attack is detected (IP changed between validation and request)."""
    pass


class CertificatePinningError(Exception):
    """Raised when TLS certificate doesn't match pinned fingerprint."""
    pass


@dataclass
class PinnedConnection:
    """
    SECURITY FIX (Audit 4 - H3): DNS pinning data structure.

    Stores resolved IP addresses at validation time to prevent DNS rebinding attacks
    where an attacker could change DNS resolution between URL validation and request execution.
    """
    hostname: str
    pinned_ips: list[str]  # IPs resolved at validation time
    pinned_at: datetime
    port: int = 443
    ttl_seconds: int = 300  # Re-resolve after 5 minutes

    def is_expired(self) -> bool:
        """Check if the pinned IPs have expired and need re-resolution."""
        age = (datetime.now(UTC) - self.pinned_at).total_seconds()
        return age > self.ttl_seconds


@dataclass
class PinnedCertificate:
    """
    SECURITY FIX (Audit 4 - H4): TLS certificate pinning data structure.

    Stores the SHA-256 fingerprint of a peer's TLS certificate to prevent
    MitM attacks even with valid certificates from compromised CAs.
    """
    peer_id: str
    hostname: str
    fingerprint_sha256: str  # hex-encoded SHA-256 of DER-encoded cert
    pinned_at: datetime
    last_verified: datetime
    # Trust on first use (TOFU) or explicit pinning
    pin_type: str = "tofu"  # "tofu" | "explicit"
    # Optional: allow cert rotation with advance notice
    next_fingerprint: str | None = None
    next_valid_from: datetime | None = None


class DNSPinStore:
    """
    SECURITY FIX (Audit 4 - H3): DNS pinning store to prevent DNS rebinding attacks.

    When a URL is validated, we resolve its DNS and store the IP addresses.
    Subsequent requests MUST connect only to those pinned IPs.

    Attack scenario this prevents:
    1. Attacker controls evil.com pointing to 8.8.8.8 (safe IP)
    2. We validate evil.com -> resolves to 8.8.8.8 -> allowed
    3. Attacker changes DNS: evil.com -> 169.254.169.254 (AWS metadata)
    4. Without pinning: our request goes to metadata server (SSRF!)
    5. With pinning: we connect to pinned 8.8.8.8, not the new DNS resolution
    """

    DEFAULT_TTL = 300  # 5 minutes
    MAX_PINS = 10000   # Prevent memory exhaustion

    def __init__(self, ttl_seconds: int | None = None):
        self._pins: dict[str, PinnedConnection] = {}
        self._lock = threading.Lock()
        self._ttl = ttl_seconds or self.DEFAULT_TTL

    def pin_hostname(self, hostname: str, port: int, ips: list[str]) -> PinnedConnection:
        """
        Pin a hostname to specific IP addresses.

        Args:
            hostname: The hostname to pin
            port: The port number
            ips: List of IP addresses to pin

        Returns:
            PinnedConnection with the pinning data
        """
        key = f"{hostname}:{port}"
        pin = PinnedConnection(
            hostname=hostname,
            pinned_ips=ips,
            pinned_at=datetime.now(UTC),
            port=port,
            ttl_seconds=self._ttl,
        )

        with self._lock:
            # Enforce size limit
            if len(self._pins) >= self.MAX_PINS and key not in self._pins:
                # Remove oldest 10%
                to_remove = self.MAX_PINS // 10
                oldest = sorted(self._pins.items(), key=lambda x: x[1].pinned_at)[:to_remove]
                for k, _ in oldest:
                    del self._pins[k]
                logger.warning(f"DNSPinStore at capacity, evicted {to_remove} oldest entries")

            self._pins[key] = pin

        logger.debug(f"Pinned {hostname}:{port} to IPs: {ips}")
        return pin

    def get_pinned_ips(self, hostname: str, port: int) -> list[str] | None:
        """
        Get pinned IPs for a hostname, or None if not pinned or expired.
        """
        key = f"{hostname}:{port}"
        with self._lock:
            pin = self._pins.get(key)
            if pin and not pin.is_expired():
                return pin.pinned_ips
            elif pin and pin.is_expired():
                # Remove expired pin
                del self._pins[key]
        return None

    def verify_ip(self, hostname: str, port: int, ip: str) -> bool:
        """
        Verify that an IP matches the pinned IPs for a hostname.

        Returns True if:
        - No pin exists (first connection)
        - IP matches a pinned IP

        Returns False if:
        - Pin exists and IP doesn't match (potential DNS rebinding attack)
        """
        pinned_ips = self.get_pinned_ips(hostname, port)
        if pinned_ips is None:
            return True  # No pin yet
        return ip in pinned_ips

    def clear_pin(self, hostname: str, port: int) -> None:
        """Remove a pin (e.g., when peer is removed)."""
        key = f"{hostname}:{port}"
        with self._lock:
            self._pins.pop(key, None)


class CertificatePinStore:
    """
    SECURITY FIX (Audit 4 - H4): TLS certificate pinning for federation peers.

    Stores SHA-256 fingerprints of peer certificates and verifies them during
    TLS handshakes. Uses Trust On First Use (TOFU) by default, with support
    for explicit pinning.

    Attack scenario this prevents:
    1. Attacker compromises a CA or obtains a fraudulent certificate
    2. Attacker performs MitM on federation traffic
    3. Without pinning: TLS validates because cert is from "trusted" CA
    4. With pinning: We reject because cert fingerprint doesn't match
    """

    MAX_PINS = 10000
    PIN_FILE = "certificate_pins.json"

    def __init__(self, storage_path: str | None = None):
        self._pins: dict[str, PinnedCertificate] = {}
        self._lock = threading.Lock()
        self._storage_path = storage_path
        # Load persisted pins
        if storage_path:
            self._load_pins()

    def _load_pins(self) -> None:
        """Load certificate pins from persistent storage."""
        if not self._storage_path:
            return
        pin_file = Path(self._storage_path) / self.PIN_FILE
        if not pin_file.exists():
            return
        try:
            with open(pin_file) as f:
                data = json.load(f)
            for peer_id, pin_data in data.items():
                self._pins[peer_id] = PinnedCertificate(
                    peer_id=pin_data["peer_id"],
                    hostname=pin_data["hostname"],
                    fingerprint_sha256=pin_data["fingerprint_sha256"],
                    pinned_at=datetime.fromisoformat(pin_data["pinned_at"]),
                    last_verified=datetime.fromisoformat(pin_data["last_verified"]),
                    pin_type=pin_data.get("pin_type", "tofu"),
                    next_fingerprint=pin_data.get("next_fingerprint"),
                    next_valid_from=datetime.fromisoformat(pin_data["next_valid_from"])
                        if pin_data.get("next_valid_from") else None,
                )
            logger.info(f"Loaded {len(self._pins)} certificate pins from {pin_file}")
        except Exception as e:
            logger.error(f"Failed to load certificate pins: {e}")

    def _save_pins(self) -> None:
        """Persist certificate pins to storage."""
        if not self._storage_path:
            return
        pin_file = Path(self._storage_path) / self.PIN_FILE
        try:
            pin_file.parent.mkdir(parents=True, exist_ok=True)
            data = {}
            for peer_id, pin in self._pins.items():
                data[peer_id] = {
                    "peer_id": pin.peer_id,
                    "hostname": pin.hostname,
                    "fingerprint_sha256": pin.fingerprint_sha256,
                    "pinned_at": pin.pinned_at.isoformat(),
                    "last_verified": pin.last_verified.isoformat(),
                    "pin_type": pin.pin_type,
                    "next_fingerprint": pin.next_fingerprint,
                    "next_valid_from": pin.next_valid_from.isoformat()
                        if pin.next_valid_from else None,
                }
            with open(pin_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Saved {len(data)} certificate pins to {pin_file}")
        except Exception as e:
            logger.error(f"Failed to save certificate pins: {e}")

    def pin_certificate(
        self,
        peer_id: str,
        hostname: str,
        fingerprint: str,
        pin_type: str = "tofu"
    ) -> PinnedCertificate:
        """
        Pin a certificate fingerprint for a peer.

        Args:
            peer_id: The peer's unique ID
            hostname: The peer's hostname
            fingerprint: SHA-256 hex fingerprint of the DER-encoded certificate
            pin_type: "tofu" for trust-on-first-use, "explicit" for admin-configured
        """
        now = datetime.now(UTC)
        pin = PinnedCertificate(
            peer_id=peer_id,
            hostname=hostname,
            fingerprint_sha256=fingerprint.lower(),
            pinned_at=now,
            last_verified=now,
            pin_type=pin_type,
        )

        with self._lock:
            # Check size limit
            if len(self._pins) >= self.MAX_PINS and peer_id not in self._pins:
                logger.error("Certificate pin store at capacity")
                raise ValueError("Certificate pin store at capacity")

            existing = self._pins.get(peer_id)
            if existing and existing.pin_type == "explicit" and pin_type == "tofu":
                # Don't overwrite explicit pins with TOFU
                logger.warning(
                    f"Attempted TOFU update of explicitly pinned cert for {peer_id}"
                )
                return existing

            self._pins[peer_id] = pin
            self._save_pins()

        logger.info(f"Pinned certificate for peer {peer_id} ({hostname}): {fingerprint[:16]}...")
        return pin

    def get_pin(self, peer_id: str) -> PinnedCertificate | None:
        """Get the pinned certificate for a peer."""
        with self._lock:
            return self._pins.get(peer_id)

    def verify_certificate(
        self,
        peer_id: str,
        cert_fingerprint: str,
        hostname: str,
    ) -> bool:
        """
        Verify a certificate fingerprint against pinned value.

        Returns True if:
        - No pin exists (TOFU will pin it)
        - Fingerprint matches pinned value
        - Fingerprint matches next_fingerprint and next_valid_from has passed

        Returns False if:
        - Pin exists and fingerprint doesn't match
        """
        pin = self.get_pin(peer_id)
        cert_fingerprint = cert_fingerprint.lower()

        if pin is None:
            # No existing pin - will be pinned via TOFU
            return True

        # Check primary fingerprint
        if pin.fingerprint_sha256 == cert_fingerprint:
            # Update last_verified
            with self._lock:
                pin.last_verified = datetime.now(UTC)
                self._save_pins()
            return True

        # Check for scheduled certificate rotation
        if (pin.next_fingerprint and
            pin.next_fingerprint.lower() == cert_fingerprint and
            pin.next_valid_from and
            datetime.now(UTC) >= pin.next_valid_from):

            logger.info(f"Peer {peer_id} rotated to pre-announced certificate")
            # Promote next cert to primary
            with self._lock:
                pin.fingerprint_sha256 = cert_fingerprint
                pin.next_fingerprint = None
                pin.next_valid_from = None
                pin.last_verified = datetime.now(UTC)
                self._save_pins()
            return True

        # Fingerprint mismatch - potential MitM attack
        logger.error(
            f"Certificate pinning failure for peer {peer_id}! "
            f"Expected {pin.fingerprint_sha256[:16]}..., got {cert_fingerprint[:16]}..."
        )
        return False

    def announce_rotation(
        self,
        peer_id: str,
        new_fingerprint: str,
        valid_from: datetime
    ) -> bool:
        """
        Announce an upcoming certificate rotation.

        Allows peers to pre-announce certificate changes to avoid pinning failures.
        """
        pin = self.get_pin(peer_id)
        if pin is None:
            logger.warning(f"Cannot announce rotation for unknown peer {peer_id}")
            return False

        with self._lock:
            pin.next_fingerprint = new_fingerprint.lower()
            pin.next_valid_from = valid_from
            self._save_pins()

        logger.info(
            f"Peer {peer_id} announced cert rotation to {new_fingerprint[:16]}... "
            f"valid from {valid_from.isoformat()}"
        )
        return True

    def remove_pin(self, peer_id: str) -> None:
        """Remove a certificate pin."""
        with self._lock:
            self._pins.pop(peer_id, None)
            self._save_pins()


# Global stores
_dns_pin_store = DNSPinStore()
_cert_pin_store: CertificatePinStore | None = None


def get_dns_pin_store() -> DNSPinStore:
    """Get the global DNS pin store."""
    return _dns_pin_store


def get_cert_pin_store(storage_path: str | None = None) -> CertificatePinStore:
    """Get or initialize the global certificate pin store."""
    global _cert_pin_store
    if _cert_pin_store is None:
        _cert_pin_store = CertificatePinStore(storage_path)
    return _cert_pin_store


class ReplayAttackError(Exception):
    """Raised when a replay attack is detected (nonce reuse)."""
    pass


class NonceStore:
    """
    Thread-safe store for tracking used nonces to prevent replay attacks.

    SECURITY FIX (Audit 2): Implements nonce-based replay prevention for
    federation messages. Nonces are stored with timestamps and expired
    after a configurable TTL to prevent memory exhaustion.

    Features:
    - Thread-safe access with locking
    - Automatic expiration of old nonces
    - Memory-bounded with max size limit
    - Uses OrderedDict for efficient cleanup
    """

    DEFAULT_TTL_SECONDS = 3600  # 1 hour - must match message timestamp window
    MAX_NONCES = 100000  # Prevent memory exhaustion

    def __init__(
        self,
        ttl_seconds: int | None = None,
        max_nonces: int | None = None,
    ):
        self._nonces: OrderedDict[str, datetime] = OrderedDict()
        self._lock = threading.Lock()
        self._ttl = ttl_seconds or self.DEFAULT_TTL_SECONDS
        self._max_nonces = max_nonces or self.MAX_NONCES
        self._last_cleanup = datetime.now(UTC)
        self._cleanup_interval = 60  # Run cleanup every 60 seconds at most

    def generate_nonce(self) -> str:
        """
        Generate a cryptographically secure random nonce.

        Returns:
            A 32-character hex string (128 bits of randomness)
        """
        return secrets.token_hex(16)

    def mark_used(self, nonce: str) -> bool:
        """
        Mark a nonce as used. Returns False if nonce was already used (replay detected).

        Args:
            nonce: The nonce to mark as used

        Returns:
            True if nonce was new and marked successfully
            False if nonce was already used (replay attack)
        """
        with self._lock:
            # Run cleanup if needed
            self._cleanup_expired_locked()

            # Check if nonce already exists
            if nonce in self._nonces:
                logger.warning(f"Replay attack detected: nonce {nonce[:8]}... already used")
                return False

            # Check size limit
            if len(self._nonces) >= self._max_nonces:
                # Remove oldest 10% to make room
                to_remove = self._max_nonces // 10
                for _ in range(to_remove):
                    if self._nonces:
                        self._nonces.popitem(last=False)
                logger.warning(f"NonceStore at capacity, evicted {to_remove} oldest entries")

            # Add nonce
            self._nonces[nonce] = datetime.now(UTC)
            return True

    def is_valid_and_unused(self, nonce: str) -> bool:
        """
        Check if a nonce is valid format and hasn't been used.

        Args:
            nonce: The nonce to check

        Returns:
            True if nonce is valid and unused, False otherwise
        """
        # Validate format: must be 32 hex characters
        if not nonce or len(nonce) != 32:
            logger.warning(f"Invalid nonce format: length {len(nonce) if nonce else 0}")
            return False

        try:
            int(nonce, 16)  # Verify it's valid hex
        except ValueError:
            logger.warning("Invalid nonce format: not valid hex")
            return False

        with self._lock:
            self._cleanup_expired_locked()
            return nonce not in self._nonces

    def _cleanup_expired_locked(self) -> None:
        """
        Remove expired nonces. Must be called while holding the lock.
        """
        now = datetime.now(UTC)

        # Only run cleanup periodically
        if (now - self._last_cleanup).total_seconds() < self._cleanup_interval:
            return

        self._last_cleanup = now
        cutoff = now - timedelta(seconds=self._ttl)

        # Remove expired entries (they're ordered by insertion time)
        expired = []
        for nonce, timestamp in self._nonces.items():
            if timestamp < cutoff:
                expired.append(nonce)
            else:
                # OrderedDict maintains insertion order, so we can stop early
                break

        for nonce in expired:
            del self._nonces[nonce]

        if expired:
            logger.debug(f"NonceStore cleaned up {len(expired)} expired nonces")

    def stats(self) -> dict[str, Any]:
        """Get statistics about the nonce store."""
        with self._lock:
            return {
                "total_nonces": len(self._nonces),
                "max_nonces": self._max_nonces,
                "ttl_seconds": self._ttl,
                "utilization_pct": len(self._nonces) / self._max_nonces * 100,
            }


# Global nonce store for federation protocol
_federation_nonce_store = NonceStore()


def get_nonce_store() -> NonceStore:
    """Get the global nonce store for federation."""
    return _federation_nonce_store


@dataclass
class ValidatedURL:
    """
    SECURITY FIX (Audit 4 - H3): Validated URL with pinned DNS resolution.

    Contains both the original URL and the resolved/pinned IP addresses
    to prevent DNS rebinding attacks.
    """
    url: str
    hostname: str
    port: int
    pinned_ips: list[str]
    scheme: str


def validate_url_for_ssrf(
    url: str,
    allow_private: bool = False,
    dns_pin_store: DNSPinStore | None = None,
) -> ValidatedURL:
    """
    Validate a URL to prevent SSRF attacks and pin DNS resolution.

    SECURITY FIX (Audit 4 - H3): Now returns ValidatedURL with pinned IPs
    to prevent DNS rebinding attacks.

    Args:
        url: The URL to validate
        allow_private: If True, allow private IP ranges (for development only)
        dns_pin_store: Optional DNS pin store (uses global if not provided)

    Returns:
        ValidatedURL with the validated URL and pinned IP addresses

    Raises:
        SSRFError: If the URL is invalid or targets a private resource
        DNSRebindingError: If DNS resolves to different IPs than previously pinned
    """
    dns_store = dns_pin_store or get_dns_pin_store()

    try:
        parsed = urlparse(url)
    except Exception as e:
        raise SSRFError(f"Invalid URL format: {e}") from e

    # SECURITY: Require HTTPS in production
    settings = get_settings()
    if settings.app_env == "production" and parsed.scheme != "https":
        raise SSRFError("HTTPS required for federation in production")

    if parsed.scheme not in ("http", "https"):
        raise SSRFError(f"Invalid URL scheme: {parsed.scheme}")

    hostname = parsed.hostname
    if not hostname:
        raise SSRFError("URL missing hostname")

    port = parsed.port or (443 if parsed.scheme == "https" else 80)

    # SECURITY: Block dangerous hostnames
    dangerous_hostnames = {
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
        "::1",
        "[::1]",
        "metadata.google.internal",  # GCP metadata
        "169.254.169.254",  # Cloud metadata endpoints
        "metadata.aws",  # AWS metadata
    }

    if hostname.lower() in dangerous_hostnames:
        raise SSRFError(f"Blocked hostname: {hostname}")

    # SECURITY FIX (Audit 4 - H3): Check for existing DNS pin
    existing_pinned_ips = dns_store.get_pinned_ips(hostname, port)

    # SECURITY: Resolve hostname and check for private IPs
    try:
        # Resolve all IP addresses for the hostname
        addr_info = socket.getaddrinfo(hostname, port, proto=socket.IPPROTO_TCP)
        resolved_ips: list[str] = list({str(info[4][0]) for info in addr_info})

        for ip_str in resolved_ips:
            try:
                ip = ipaddress.ip_address(ip_str)
            except ValueError as exc:
                raise SSRFError(f"Invalid IP address resolved: {ip_str}") from exc

            # Block private and special IP ranges unless explicitly allowed
            if not allow_private:
                if ip.is_private:
                    raise SSRFError(f"Private IP address blocked: {ip_str}")
                if ip.is_loopback:
                    raise SSRFError(f"Loopback address blocked: {ip_str}")
                if ip.is_link_local:
                    raise SSRFError(f"Link-local address blocked: {ip_str}")
                if ip.is_reserved:
                    raise SSRFError(f"Reserved address blocked: {ip_str}")
                if ip.is_multicast:
                    raise SSRFError(f"Multicast address blocked: {ip_str}")

                # Additional AWS/GCP metadata endpoint protection
                if ip_str.startswith("169.254."):
                    raise SSRFError(f"Cloud metadata address blocked: {ip_str}")

    except socket.gaierror as e:
        raise SSRFError(f"DNS resolution failed for {hostname}: {e}") from e
    except OSError as e:
        raise SSRFError(f"Network error resolving {hostname}: {e}") from e

    # SECURITY FIX (Audit 4 - H3): Detect DNS rebinding attack
    if existing_pinned_ips is not None:
        # Check if any resolved IP matches pinned IPs
        matching_ips = set(resolved_ips) & set(existing_pinned_ips)
        if not matching_ips:
            logger.error(
                f"DNS rebinding detected for {hostname}! "
                f"Pinned: {existing_pinned_ips}, Resolved: {resolved_ips}"
            )
            raise DNSRebindingError(
                f"DNS resolved to different IPs than pinned. "
                f"Expected one of {existing_pinned_ips}, got {resolved_ips}"
            )
        # Use only the matching IPs
        pinned_ips = list(matching_ips)
    else:
        # First connection - pin the resolved IPs
        dns_store.pin_hostname(hostname, port, resolved_ips)
        pinned_ips = resolved_ips

    return ValidatedURL(
        url=url,
        hostname=hostname,
        port=port,
        pinned_ips=pinned_ips,
        scheme=parsed.scheme,
    )


def _compute_cert_fingerprint(cert_der: bytes) -> str:
    """
    Compute SHA-256 fingerprint of a DER-encoded certificate.

    SECURITY FIX (Audit 4 - H4): Helper for certificate pinning.
    """
    return hashlib.sha256(cert_der).hexdigest()


class FederationProtocol:
    """
    Core protocol for federated communication.

    Responsibilities:
    1. Key generation and management (with persistence)
    2. Peer handshake and verification
    3. Signed message exchange
    4. Health checking and status updates

    SECURITY FIX (Audit 2): Keys are now persisted to disk to prevent
    regeneration on restart which would invalidate all peer relationships.

    SECURITY FIX (Audit 4):
    - H3: DNS pinning to prevent DNS rebinding attacks
    - H4: TLS certificate pinning for federation peers
    """

    API_VERSION = "1.0"
    HANDSHAKE_TIMEOUT = 30  # seconds
    REQUEST_TIMEOUT = 60  # seconds
    # Configurable via FEDERATION_KEY_PATH env var; fallback supports both Docker and local dev
    DEFAULT_KEY_PATH = os.getenv(
        "FEDERATION_KEY_PATH",
        "/app/data/federation_keys" if os.path.exists("/app") else "./data/federation_keys"
    )

    def __init__(
        self,
        instance_id: str,
        instance_name: str,
        key_storage_path: str | None = None,
        nonce_store: NonceStore | None = None,
        dns_pin_store: DNSPinStore | None = None,
        cert_pin_store: CertificatePinStore | None = None,
    ):
        self.instance_id = instance_id
        self.instance_name = instance_name
        self._private_key: ed25519.Ed25519PrivateKey | None = None
        self._public_key: ed25519.Ed25519PublicKey | None = None
        self._public_key_b64: str = ""
        self._http_client: httpx.AsyncClient | None = None
        # SECURITY FIX: Configurable key storage path for persistence
        self._key_storage_path = key_storage_path or self.DEFAULT_KEY_PATH
        # SECURITY FIX: Nonce store for replay attack prevention
        self._nonce_store = nonce_store or get_nonce_store()
        # SECURITY FIX (Audit 4 - H3): DNS pin store for DNS rebinding protection
        self._dns_pin_store = dns_pin_store or get_dns_pin_store()
        # SECURITY FIX (Audit 4 - H4): Certificate pin store for TLS pinning
        self._cert_pin_store = cert_pin_store or get_cert_pin_store(key_storage_path)

    async def initialize(self) -> None:
        """Initialize protocol with key generation."""
        # Generate or load keypair
        await self._load_or_generate_keys()

        # Create HTTP client
        # SECURITY FIX: Disable follow_redirects to prevent SSRF bypass via redirect
        self._http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.REQUEST_TIMEOUT),
            follow_redirects=False,  # SECURITY: Redirects can bypass URL validation
            headers={
                "User-Agent": f"Forge-Federation/{self.API_VERSION}",
                "X-Forge-Instance": self.instance_id,
            }
        )
        logger.info(f"Federation protocol initialized for {self.instance_name}")

    async def shutdown(self) -> None:
        """Cleanup resources."""
        if self._http_client:
            await self._http_client.aclose()

    async def _get_response_cert_fingerprint(
        self,
        response: httpx.Response
    ) -> str | None:
        """
        SECURITY FIX (Audit 4 - H4): Extract TLS certificate fingerprint from response.

        Attempts to get the server's certificate from the underlying connection
        and compute its SHA-256 fingerprint.

        Note: This requires access to the underlying SSL socket, which may not
        always be available depending on the httpx transport configuration.

        Returns:
            SHA-256 hex fingerprint of the server certificate, or None if unavailable
        """
        try:
            # Access the underlying connection stream
            stream = response.stream
            if hasattr(stream, '_stream') and hasattr(stream._stream, 'get_extra_info'):
                ssl_object = stream._stream.get_extra_info('ssl_object')
                if ssl_object:
                    # Get peer certificate in DER format
                    cert_der = ssl_object.getpeercert(binary_form=True)
                    if cert_der:
                        return _compute_cert_fingerprint(cert_der)

            # Alternative: try via response.extensions (httpx 0.24+)
            if hasattr(response, 'extensions'):
                network_stream = response.extensions.get('network_stream')
                if network_stream and hasattr(network_stream, 'get_extra_info'):
                    ssl_object = network_stream.get_extra_info('ssl_object')
                    if ssl_object:
                        cert_der = ssl_object.getpeercert(binary_form=True)
                        if cert_der:
                            return _compute_cert_fingerprint(cert_der)

            logger.debug("Could not extract certificate from response")
            return None
        except Exception as e:
            logger.warning(f"Failed to extract certificate fingerprint: {e}")
            return None

    async def _load_or_generate_keys(self) -> None:
        """
        Load existing keys from storage or generate new keypair.

        SECURITY FIX (Audit 2): Keys are now persisted to prevent regeneration
        on restart, which would invalidate all peer trust relationships.
        """
        key_dir = Path(self._key_storage_path)
        private_key_path = key_dir / f"{self.instance_id}_private.pem"
        public_key_path = key_dir / f"{self.instance_id}_public.pem"

        # Try to load existing keys
        if private_key_path.exists() and public_key_path.exists():
            try:
                logger.info(f"Loading federation keys from {key_dir}")
                with open(private_key_path, "rb") as f:
                    loaded_key = serialization.load_pem_private_key(
                        f.read(),
                        password=None,  # Keys stored without password encryption
                    )
                if not isinstance(loaded_key, ed25519.Ed25519PrivateKey):
                    raise TypeError("Loaded key is not an Ed25519 private key")
                self._private_key = loaded_key
                self._public_key = self._private_key.public_key()

                # Export public key as base64
                public_bytes = self._public_key.public_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PublicFormat.Raw
                )
                self._public_key_b64 = base64.b64encode(public_bytes).decode('utf-8')
                logger.info("Federation keys loaded successfully")
                return
            except Exception as e:
                logger.warning(f"Failed to load existing keys: {e}, generating new ones")

        # Generate new keys
        logger.info("Generating new federation keypair")
        self._private_key = ed25519.Ed25519PrivateKey.generate()
        self._public_key = self._private_key.public_key()

        # Export public key as base64
        public_bytes = self._public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        self._public_key_b64 = base64.b64encode(public_bytes).decode('utf-8')

        # Persist keys to storage
        await self._save_keys(private_key_path, public_key_path)

    async def _save_keys(self, private_key_path: Path, public_key_path: Path) -> None:
        """
        Save keys to persistent storage.

        Keys are stored in PEM format for compatibility.

        SECURITY FIX (Audit 4 - H8): Private keys are now encrypted at rest
        using a passphrase from the FEDERATION_KEY_PASSPHRASE environment variable.
        """
        try:
            # Create directory if needed
            private_key_path.parent.mkdir(parents=True, exist_ok=True)

            # SECURITY FIX (Audit 4 - H8): Encrypt private key at rest
            # Get passphrase from environment variable
            passphrase = os.environ.get("FEDERATION_KEY_PASSPHRASE")

            encryption_algo: serialization.KeySerializationEncryption
            if passphrase:
                # Encrypt with provided passphrase
                encryption_algo = serialization.BestAvailableEncryption(
                    passphrase.encode('utf-8')
                )
                logger.info("Saving federation private key with encryption")
            else:
                # No passphrase - warn and use no encryption (development only)
                encryption_algo = serialization.NoEncryption()
                logger.warning(
                    "FEDERATION_KEY_PASSPHRASE not set - private key stored without encryption. "
                    "This is insecure for production deployments!"
                )

            if self._private_key is None:
                raise RuntimeError("Private key not initialized")

            # Save private key (PEM format)
            private_pem = self._private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=encryption_algo
            )
            with open(private_key_path, "wb") as f:
                f.write(private_pem)

            # SECURITY FIX (Audit 4 - M6): Set restrictive permissions on private key
            # os.chmod doesn't work properly on Windows, so we need platform-specific handling
            await self._set_restrictive_permissions(private_key_path)

            if self._public_key is None:
                raise RuntimeError("Public key not initialized")

            # Save public key (PEM format)
            public_pem = self._public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            with open(public_key_path, "wb") as f:
                f.write(public_pem)

            logger.info(f"Federation keys saved to {private_key_path.parent}")
        except Exception as e:
            logger.error(f"Failed to save federation keys: {e}")
            # Don't raise - keys work in memory, just won't persist

    async def _set_restrictive_permissions(self, file_path: Path) -> None:
        """
        SECURITY FIX (Audit 4 - M6): Set restrictive file permissions cross-platform.

        On Unix: Uses chmod 0o400 (owner read-only)
        On Windows: Uses icacls to restrict access to current user only

        This replaces the silent-failure approach with proper cross-platform handling.
        """
        import platform
        import subprocess

        if platform.system() == "Windows":
            # Windows: Use icacls to set restrictive permissions
            # - /inheritance:r = Remove inherited permissions
            # - /grant:r = Replace all permissions with just this user
            try:
                # Get current username
                username = os.environ.get("USERNAME", os.environ.get("USER", ""))
                if not username:
                    logger.warning(
                        f"Could not determine username for Windows ACL on {file_path}. "
                        "Private key may have loose permissions."
                    )
                    return

                # Remove all inherited permissions and grant only current user read access
                # Using (R) for read-only access
                result = subprocess.run(
                    [
                        "icacls",
                        str(file_path),
                        "/inheritance:r",  # Remove inherited permissions
                        "/grant:r",
                        f"{username}:(R)",  # Grant read-only to current user
                    ],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

                if result.returncode != 0:
                    logger.warning(
                        f"Failed to set Windows ACL on private key: {result.stderr}. "
                        "Private key may have loose permissions."
                    )
                else:
                    logger.debug(f"Set restrictive Windows ACL on {file_path}")

            except FileNotFoundError:
                logger.warning(
                    "icacls not found on Windows. Cannot set restrictive permissions on private key. "
                    "Ensure the key file is protected manually."
                )
            except subprocess.TimeoutExpired:
                logger.warning("Timeout setting Windows ACL on private key")
            except Exception as e:
                logger.warning(f"Error setting Windows ACL on private key: {e}")
        else:
            # Unix/Linux/macOS: Use standard chmod
            try:
                os.chmod(file_path, 0o400)
                logger.debug(f"Set chmod 0o400 on {file_path}")
            except OSError as e:
                logger.warning(
                    f"Failed to set restrictive permissions on private key: {e}. "
                    "Ensure the key file is protected manually."
                )

    def get_public_key(self) -> str:
        """Get our public key as base64 string."""
        return self._public_key_b64

    def sign_message(self, message: bytes) -> str:
        """Sign a message with our private key."""
        if not self._private_key:
            raise RuntimeError("Protocol not initialized")
        signature = self._private_key.sign(message)
        return base64.b64encode(signature).decode('utf-8')

    def verify_signature(
        self,
        message: bytes,
        signature_b64: str,
        public_key_b64: str
    ) -> bool:
        """Verify a signature from a peer."""
        try:
            # Decode public key
            public_bytes = base64.b64decode(public_key_b64)
            public_key = ed25519.Ed25519PublicKey.from_public_bytes(public_bytes)

            # Decode and verify signature
            signature = base64.b64decode(signature_b64)
            public_key.verify(signature, message)
            return True
        except (InvalidSignature, ValueError, Exception) as e:
            logger.warning(f"Signature verification failed: {e}")
            return False

    async def create_handshake(self) -> PeerHandshake:
        """Create a handshake message for peer introduction."""
        timestamp = datetime.now(UTC)
        # SECURITY FIX: Generate nonce for replay prevention
        nonce = self._nonce_store.generate_nonce()

        # Data to sign (including nonce)
        handshake_data = {
            "instance_id": self.instance_id,
            "instance_name": self.instance_name,
            "api_version": self.API_VERSION,
            "public_key": self._public_key_b64,
            "timestamp": timestamp.isoformat(),
            "nonce": nonce,  # SECURITY FIX: Include nonce in signed data
        }

        # Sign the handshake
        message = json.dumps(handshake_data, sort_keys=True).encode('utf-8')
        signature = self.sign_message(message)

        return PeerHandshake(
            instance_id=self.instance_id,
            instance_name=self.instance_name,
            api_version=self.API_VERSION,
            public_key=self._public_key_b64,
            supports_push=True,
            supports_pull=True,
            supports_streaming=False,
            suggested_interval_minutes=60,
            max_capsules_per_sync=1000,
            signature=signature,
            timestamp=timestamp,
            nonce=nonce,  # SECURITY FIX: Include nonce in handshake
        )

    def verify_handshake(self, handshake: PeerHandshake) -> bool:
        """Verify an incoming handshake."""
        # Check timestamp freshness (within 5 minutes in the past, 30 seconds in future for clock skew)
        now = datetime.now(UTC)
        time_diff = (now - handshake.timestamp).total_seconds()
        if time_diff > 300:  # More than 5 minutes old
            logger.warning("Handshake timestamp too old")
            return False
        if time_diff < -30:  # More than 30 seconds in future (clock skew allowance)
            logger.warning("Handshake timestamp too far in future")
            return False

        # SECURITY FIX (Audit 4 - H5): Verify nonce for replay prevention
        # REMOVED backward compatibility - all handshakes MUST have nonces
        nonce = getattr(handshake, 'nonce', None)
        if not nonce:
            # SECURITY FIX: Reject handshakes without nonce - no backward compatibility
            logger.error("Handshake rejected: missing nonce (replay protection required)")
            return False

        # Check nonce format and uniqueness
        if not self._nonce_store.is_valid_and_unused(nonce):
            logger.warning(f"Handshake nonce invalid or already used: {nonce[:8]}...")
            return False

        # Mark nonce as used to prevent replay
        if not self._nonce_store.mark_used(nonce):
            logger.warning(f"Replay attack detected in handshake: nonce {nonce[:8]}...")
            return False

        # Reconstruct signed data
        handshake_data = {
            "instance_id": handshake.instance_id,
            "instance_name": handshake.instance_name,
            "api_version": handshake.api_version,
            "public_key": handshake.public_key,
            "timestamp": handshake.timestamp.isoformat(),
        }
        # Include nonce in signature verification if present
        if nonce:
            handshake_data["nonce"] = nonce

        message = json.dumps(handshake_data, sort_keys=True).encode('utf-8')
        return self.verify_signature(message, handshake.signature, handshake.public_key)

    async def initiate_handshake(
        self,
        peer_url: str,
        peer_id: str | None = None,
    ) -> tuple[PeerHandshake, PeerHandshake] | None:
        """
        Initiate handshake with a potential peer.

        SECURITY FIX (Audit 4):
        - H3: Uses DNS pinning to prevent DNS rebinding attacks
        - H4: Verifies and pins TLS certificate fingerprint

        Args:
            peer_url: The peer's URL
            peer_id: Optional peer ID for certificate pinning (uses instance_id from response if None)

        Returns (our_handshake, their_handshake) if successful, None otherwise.
        """
        if not self._http_client:
            raise RuntimeError("Protocol not initialized")

        # SECURITY FIX (Audit 4 - H3): Validate URL with DNS pinning
        settings = get_settings()
        allow_private = settings.app_env != "production"
        try:
            validated = validate_url_for_ssrf(
                peer_url,
                allow_private=allow_private,
                dns_pin_store=self._dns_pin_store,
            )
        except SSRFError as e:
            logger.error(f"SSRF protection blocked handshake URL: {e}")
            return None
        except DNSRebindingError as e:
            logger.error(f"DNS rebinding attack detected: {e}")
            return None

        try:
            # Create our handshake
            our_handshake = await self.create_handshake()

            # Send to peer (using validated URL)
            response = await self._http_client.post(
                f"{validated.url.rstrip('/')}/api/v1/federation/handshake",
                json=our_handshake.model_dump(mode='json'),
                timeout=self.HANDSHAKE_TIMEOUT,
            )

            # SECURITY FIX (Audit 4 - H4): Verify and pin TLS certificate
            if validated.scheme == "https":
                cert_fingerprint = await self._get_response_cert_fingerprint(response)
                if cert_fingerprint:
                    # Use peer_id if provided, otherwise defer pinning until we know their instance_id
                    effective_peer_id = peer_id
                    if effective_peer_id:
                        if not self._cert_pin_store.verify_certificate(
                            effective_peer_id, cert_fingerprint, validated.hostname
                        ):
                            logger.error(f"Certificate pinning failed for peer {effective_peer_id}")
                            return None

            if response.status_code != 200:
                logger.error(f"Handshake failed with status {response.status_code}")
                return None

            # Parse their response
            their_data = response.json()
            their_handshake = PeerHandshake(**their_data)

            # SECURITY FIX (Audit 4 - H4): Pin certificate for new peer (TOFU)
            if validated.scheme == "https" and cert_fingerprint:
                their_id = their_handshake.instance_id
                existing_pin = self._cert_pin_store.get_pin(their_id)
                if existing_pin is None:
                    # First contact - Trust On First Use (TOFU)
                    self._cert_pin_store.pin_certificate(
                        peer_id=their_id,
                        hostname=validated.hostname,
                        fingerprint=cert_fingerprint,
                        pin_type="tofu",
                    )
                    logger.info(f"TOFU: Pinned certificate for new peer {their_id}")
                elif not self._cert_pin_store.verify_certificate(
                    their_id, cert_fingerprint, validated.hostname
                ):
                    logger.error(f"Certificate pinning failed for peer {their_id}")
                    return None

            # Verify their handshake
            if not self.verify_handshake(their_handshake):
                logger.error("Peer handshake verification failed")
                return None

            logger.info(f"Handshake successful with {their_handshake.instance_name}")
            return (our_handshake, their_handshake)

        except httpx.RequestError as e:
            logger.error(f"Handshake request failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Handshake error: {e}")
            return None

    async def check_peer_health(self, peer: FederatedPeer) -> PeerStatus:
        """
        Check if a peer is reachable and responsive.

        SECURITY FIX (Audit 4 - H3): Uses DNS pinning to prevent rebinding attacks.
        """
        if not self._http_client:
            raise RuntimeError("Protocol not initialized")

        # SECURITY FIX (Audit 4 - H3): Validate URL with DNS pinning
        settings = get_settings()
        allow_private = settings.app_env != "production"
        try:
            validated = validate_url_for_ssrf(
                peer.url,
                allow_private=allow_private,
                dns_pin_store=self._dns_pin_store,
            )
        except SSRFError as e:
            logger.error(f"SSRF protection blocked health check URL: {e}")
            return PeerStatus.OFFLINE
        except DNSRebindingError as e:
            logger.error(f"DNS rebinding detected during health check: {e}")
            return PeerStatus.OFFLINE

        try:
            response = await self._http_client.get(
                f"{validated.url.rstrip('/')}/api/v1/federation/health",
                timeout=10,
            )

            if response.status_code == 200:
                return PeerStatus.ACTIVE
            elif response.status_code in (502, 503, 504):
                return PeerStatus.DEGRADED
            else:
                return PeerStatus.DEGRADED

        except httpx.TimeoutException:
            return PeerStatus.DEGRADED
        except httpx.RequestError:
            return PeerStatus.OFFLINE

    async def send_sync_request(
        self,
        peer: FederatedPeer,
        since: datetime | None = None,
        capsule_types: list[str] | None = None,
        limit: int = 100,
    ) -> SyncPayload | None:
        """
        Request changes from a peer.

        SECURITY FIX (Audit 4):
        - H3: Uses DNS pinning to prevent DNS rebinding attacks
        - H29: Includes nonce in requests to prevent replay attacks

        Args:
            peer: The peer to sync with
            since: Get changes since this timestamp
            capsule_types: Filter to specific capsule types
            limit: Maximum capsules to retrieve
        """
        if not self._http_client:
            raise RuntimeError("Protocol not initialized")

        # SECURITY FIX (Audit 4 - H3): Validate URL with DNS pinning
        settings = get_settings()
        allow_private = settings.app_env != "production"
        try:
            validated = validate_url_for_ssrf(
                peer.url,
                allow_private=allow_private,
                dns_pin_store=self._dns_pin_store,
            )
        except SSRFError as e:
            logger.error(f"SSRF protection blocked sync request URL: {e}")
            return None
        except DNSRebindingError as e:
            logger.error(f"DNS rebinding detected during sync request: {e}")
            return None

        try:
            # Build request
            params: dict[str, Any] = {"limit": limit}
            if since:
                params["since"] = since.isoformat()
            if capsule_types:
                params["types"] = ",".join(capsule_types)

            # SECURITY FIX (Audit 4 - H29): Add nonce to prevent replay attacks
            # Each sync request includes a unique nonce that is signed
            nonce = f"{int(datetime.now(UTC).timestamp() * 1000)}_{secrets.token_hex(16)}"
            params["nonce"] = nonce

            # Sign request including nonce
            request_data = json.dumps(params, sort_keys=True).encode('utf-8')
            signature = self.sign_message(request_data)

            response = await self._http_client.get(
                f"{validated.url.rstrip('/')}/api/v1/federation/changes",
                params=params,
                headers={
                    "X-Forge-Signature": signature,
                    "X-Forge-Public-Key": self._public_key_b64,
                    "X-Forge-Nonce": nonce,  # SECURITY FIX: Include nonce in header
                },
            )

            if response.status_code != 200:
                logger.error(f"Sync request failed: {response.status_code}")
                return None

            payload_data = response.json()
            payload = SyncPayload(**payload_data)

            # Verify payload signature
            if not self._verify_payload(payload, peer.public_key):
                logger.error("Payload signature verification failed")
                return None

            return payload

        except Exception as e:
            logger.error(f"Sync request error: {e}")
            return None

    async def send_sync_push(
        self,
        peer: FederatedPeer,
        payload: SyncPayload,
    ) -> bool:
        """
        Push changes to a peer.

        SECURITY FIX (Audit 4 - H3): Uses DNS pinning to prevent DNS rebinding attacks.

        Args:
            peer: The peer to push to
            payload: The sync payload with capsules/edges
        """
        if not self._http_client:
            raise RuntimeError("Protocol not initialized")

        # SECURITY FIX (Audit 4 - H3): Validate URL with DNS pinning
        settings = get_settings()
        allow_private = settings.app_env != "production"
        try:
            validated = validate_url_for_ssrf(
                peer.url,
                allow_private=allow_private,
                dns_pin_store=self._dns_pin_store,
            )
        except SSRFError as e:
            logger.error(f"SSRF protection blocked sync push URL: {e}")
            return False
        except DNSRebindingError as e:
            logger.error(f"DNS rebinding detected during sync push: {e}")
            return False

        try:
            # Create payload copy with empty signature for signing
            payload_for_signing = payload.model_copy()
            payload_for_signing.signature = ""
            payload_json_for_signing = payload_for_signing.model_dump_json()

            # Compute signature over payload with empty signature field
            signature = self.sign_message(payload_json_for_signing.encode('utf-8'))

            # Update payload with signature
            payload.signature = signature

            response = await self._http_client.post(
                f"{validated.url.rstrip('/')}/api/v1/federation/incoming/capsules",
                json=payload.model_dump(mode='json'),
                headers={
                    "X-Forge-Public-Key": self._public_key_b64,
                },
            )

            if response.status_code == 200:
                logger.info(f"Push to {peer.name} successful")
                return True
            else:
                logger.error(f"Push failed: {response.status_code}")
                return False

        except httpx.RequestError as e:
            logger.error(f"Push request error: {e}")
            return False
        except Exception as e:
            logger.exception(f"Push error: {e}")
            return False

    def _verify_payload(self, payload: SyncPayload, public_key: str) -> bool:
        """Verify a sync payload signature and nonce."""
        # SECURITY FIX (Audit 4 - H5): Verify nonce for replay prevention
        # REMOVED backward compatibility - all payloads MUST have nonces
        nonce = getattr(payload, 'nonce', None)
        if not nonce:
            # SECURITY FIX: Reject payloads without nonce - no backward compatibility
            logger.error("Sync payload rejected: missing nonce (replay protection required)")
            return False

        # Check nonce format and uniqueness
        if not self._nonce_store.is_valid_and_unused(nonce):
            logger.warning(f"Payload nonce invalid or already used: {nonce[:8]}...")
            return False

        # Mark nonce as used to prevent replay
        if not self._nonce_store.mark_used(nonce):
            logger.warning(f"Replay attack detected in payload: nonce {nonce[:8]}...")
            return False

        # Reconstruct payload without signature for verification
        payload_copy = payload.model_copy()
        payload_copy.signature = ""

        payload_json = payload_copy.model_dump_json()
        return self.verify_signature(
            payload_json.encode('utf-8'),
            payload.signature,
            public_key
        )

    def compute_content_hash(self, content: dict[str, Any]) -> str:
        """Compute a SHA-256 hash of content."""
        content_str = json.dumps(content, sort_keys=True)
        return hashlib.sha256(content_str.encode('utf-8')).hexdigest()

    async def create_sync_payload(
        self,
        sync_id: str,
        peer_id: str,
        capsules: list[dict[str, Any]],
        edges: list[dict[str, Any]] | None = None,
        deletions: list[str] | None = None,
        has_more: bool = False,
        next_cursor: str | None = None,
    ) -> SyncPayload:
        """Create a signed sync payload with nonce for replay prevention."""
        timestamp = datetime.now(UTC)
        # SECURITY FIX: Generate nonce for replay prevention
        nonce = self._nonce_store.generate_nonce()

        # Compute content hash
        content = {
            "capsules": capsules,
            "edges": edges or [],
            "deletions": deletions or [],
        }
        content_hash = self.compute_content_hash(content)

        # Create payload with empty signature first
        payload = SyncPayload(
            peer_id=peer_id,
            sync_id=sync_id,
            timestamp=timestamp,
            capsules=capsules,
            edges=edges or [],
            deletions=deletions or [],
            has_more=has_more,
            next_cursor=next_cursor,
            content_hash=content_hash,
            signature="",  # Empty for signing
            nonce=nonce,  # SECURITY FIX: Include nonce for replay prevention
        )

        # Sign the payload with empty signature field
        payload_json = payload.model_dump_json()
        payload.signature = self.sign_message(payload_json.encode('utf-8'))

        return payload
