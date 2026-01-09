"""
Federation Protocol

Handles peer discovery, handshake, and secure communication between Forge instances.

SECURITY FIXES (Audit 2):
- Added SSRF protection for peer URLs
- Disabled redirect following to prevent SSRF bypass
- Added private IP range blocking
- Added nonce-based replay prevention
"""

import asyncio
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
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidSignature

from forge.federation.models import (
    FederatedPeer,
    PeerHandshake,
    SyncPayload,
    PeerStatus,
    SyncDirection,
)
from forge.config import get_settings

logger = logging.getLogger(__name__)


class SSRFError(Exception):
    """Raised when a potential SSRF attack is detected."""
    pass


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
        self._last_cleanup = datetime.now(timezone.utc)
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
            self._nonces[nonce] = datetime.now(timezone.utc)
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
            logger.warning(f"Invalid nonce format: not valid hex")
            return False

        with self._lock:
            self._cleanup_expired_locked()
            return nonce not in self._nonces

    def _cleanup_expired_locked(self) -> None:
        """
        Remove expired nonces. Must be called while holding the lock.
        """
        now = datetime.now(timezone.utc)

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


def validate_url_for_ssrf(url: str, allow_private: bool = False) -> str:
    """
    Validate a URL to prevent SSRF attacks.

    Args:
        url: The URL to validate
        allow_private: If True, allow private IP ranges (for development only)

    Returns:
        The validated URL

    Raises:
        SSRFError: If the URL is invalid or targets a private resource
    """
    try:
        parsed = urlparse(url)
    except Exception as e:
        raise SSRFError(f"Invalid URL format: {e}")

    # SECURITY: Require HTTPS in production
    settings = get_settings()
    if settings.environment == "production" and parsed.scheme != "https":
        raise SSRFError("HTTPS required for federation in production")

    if parsed.scheme not in ("http", "https"):
        raise SSRFError(f"Invalid URL scheme: {parsed.scheme}")

    hostname = parsed.hostname
    if not hostname:
        raise SSRFError("URL missing hostname")

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

    # SECURITY: Resolve hostname and check for private IPs
    try:
        # Resolve all IP addresses for the hostname
        addr_info = socket.getaddrinfo(hostname, parsed.port or 443, proto=socket.IPPROTO_TCP)
        ip_addresses = set(info[4][0] for info in addr_info)

        for ip_str in ip_addresses:
            try:
                ip = ipaddress.ip_address(ip_str)
            except ValueError:
                raise SSRFError(f"Invalid IP address resolved: {ip_str}")

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
        raise SSRFError(f"DNS resolution failed for {hostname}: {e}")
    except OSError as e:
        raise SSRFError(f"Network error resolving {hostname}: {e}")

    return url


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
    """

    API_VERSION = "1.0"
    HANDSHAKE_TIMEOUT = 30  # seconds
    REQUEST_TIMEOUT = 60  # seconds
    DEFAULT_KEY_PATH = "/app/data/federation_keys"  # Docker volume mount point

    def __init__(
        self,
        instance_id: str,
        instance_name: str,
        key_storage_path: str | None = None,
        nonce_store: NonceStore | None = None,
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
                    self._private_key = serialization.load_pem_private_key(
                        f.read(),
                        password=None,  # Keys stored without password encryption
                    )
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
        """
        try:
            # Create directory if needed
            private_key_path.parent.mkdir(parents=True, exist_ok=True)

            # Save private key (PEM format, no encryption)
            private_pem = self._private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
            with open(private_key_path, "wb") as f:
                f.write(private_pem)

            # Set restrictive permissions on private key (owner read only)
            try:
                os.chmod(private_key_path, 0o400)
            except OSError:
                pass  # May fail on Windows

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
        timestamp = datetime.now(timezone.utc)
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
        now = datetime.now(timezone.utc)
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

    async def initiate_handshake(self, peer_url: str) -> tuple[PeerHandshake, PeerHandshake] | None:
        """
        Initiate handshake with a potential peer.

        Returns (our_handshake, their_handshake) if successful, None otherwise.
        """
        if not self._http_client:
            raise RuntimeError("Protocol not initialized")

        # SECURITY FIX: Validate URL to prevent SSRF attacks
        settings = get_settings()
        allow_private = settings.environment != "production"
        try:
            validated_url = validate_url_for_ssrf(peer_url, allow_private=allow_private)
        except SSRFError as e:
            logger.error(f"SSRF protection blocked handshake URL: {e}")
            return None

        try:
            # Create our handshake
            our_handshake = await self.create_handshake()

            # Send to peer (using validated URL)
            response = await self._http_client.post(
                f"{validated_url.rstrip('/')}/api/v1/federation/handshake",
                json=our_handshake.model_dump(mode='json'),
                timeout=self.HANDSHAKE_TIMEOUT,
            )

            if response.status_code != 200:
                logger.error(f"Handshake failed with status {response.status_code}")
                return None

            # Parse their response
            their_data = response.json()
            their_handshake = PeerHandshake(**their_data)

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
        """Check if a peer is reachable and responsive."""
        if not self._http_client:
            raise RuntimeError("Protocol not initialized")

        # SECURITY FIX: Validate URL to prevent SSRF attacks
        settings = get_settings()
        allow_private = settings.environment != "production"
        try:
            validated_url = validate_url_for_ssrf(peer.url, allow_private=allow_private)
        except SSRFError as e:
            logger.error(f"SSRF protection blocked health check URL: {e}")
            return PeerStatus.OFFLINE

        try:
            response = await self._http_client.get(
                f"{validated_url.rstrip('/')}/api/v1/federation/health",
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

        Args:
            peer: The peer to sync with
            since: Get changes since this timestamp
            capsule_types: Filter to specific capsule types
            limit: Maximum capsules to retrieve
        """
        if not self._http_client:
            raise RuntimeError("Protocol not initialized")

        # SECURITY FIX: Validate URL to prevent SSRF attacks
        settings = get_settings()
        allow_private = settings.environment != "production"
        try:
            validated_url = validate_url_for_ssrf(peer.url, allow_private=allow_private)
        except SSRFError as e:
            logger.error(f"SSRF protection blocked sync request URL: {e}")
            return None

        try:
            # Build request
            params: dict[str, Any] = {"limit": limit}
            if since:
                params["since"] = since.isoformat()
            if capsule_types:
                params["types"] = ",".join(capsule_types)

            # Sign request
            request_data = json.dumps(params, sort_keys=True).encode('utf-8')
            signature = self.sign_message(request_data)

            response = await self._http_client.get(
                f"{validated_url.rstrip('/')}/api/v1/federation/changes",
                params=params,
                headers={
                    "X-Forge-Signature": signature,
                    "X-Forge-Public-Key": self._public_key_b64,
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

        Args:
            peer: The peer to push to
            payload: The sync payload with capsules/edges
        """
        if not self._http_client:
            raise RuntimeError("Protocol not initialized")

        # SECURITY FIX: Validate URL to prevent SSRF attacks
        settings = get_settings()
        allow_private = settings.environment != "production"
        try:
            validated_url = validate_url_for_ssrf(peer.url, allow_private=allow_private)
        except SSRFError as e:
            logger.error(f"SSRF protection blocked sync push URL: {e}")
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
                f"{validated_url.rstrip('/')}/api/v1/federation/incoming/capsules",
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
        timestamp = datetime.now(timezone.utc)
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
