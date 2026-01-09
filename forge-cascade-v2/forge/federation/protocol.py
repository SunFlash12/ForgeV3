"""
Federation Protocol

Handles peer discovery, handshake, and secure communication between Forge instances.
"""

import asyncio
import base64
import hashlib
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Any

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


class FederationProtocol:
    """
    Core protocol for federated communication.

    Responsibilities:
    1. Key generation and management
    2. Peer handshake and verification
    3. Signed message exchange
    4. Health checking and status updates
    """

    API_VERSION = "1.0"
    HANDSHAKE_TIMEOUT = 30  # seconds
    REQUEST_TIMEOUT = 60  # seconds

    def __init__(self, instance_id: str, instance_name: str):
        self.instance_id = instance_id
        self.instance_name = instance_name
        self._private_key: ed25519.Ed25519PrivateKey | None = None
        self._public_key: ed25519.Ed25519PublicKey | None = None
        self._public_key_b64: str = ""
        self._http_client: httpx.AsyncClient | None = None

    async def initialize(self) -> None:
        """Initialize protocol with key generation."""
        # Generate or load keypair
        await self._load_or_generate_keys()

        # Create HTTP client
        self._http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.REQUEST_TIMEOUT),
            follow_redirects=True,
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
        """Load existing keys or generate new keypair."""
        # In production, load from secure storage
        # For now, generate fresh keys
        self._private_key = ed25519.Ed25519PrivateKey.generate()
        self._public_key = self._private_key.public_key()

        # Export public key as base64
        public_bytes = self._public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        self._public_key_b64 = base64.b64encode(public_bytes).decode('utf-8')

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

        # Data to sign
        handshake_data = {
            "instance_id": self.instance_id,
            "instance_name": self.instance_name,
            "api_version": self.API_VERSION,
            "public_key": self._public_key_b64,
            "timestamp": timestamp.isoformat(),
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

        # Reconstruct signed data
        handshake_data = {
            "instance_id": handshake.instance_id,
            "instance_name": handshake.instance_name,
            "api_version": handshake.api_version,
            "public_key": handshake.public_key,
            "timestamp": handshake.timestamp.isoformat(),
        }

        message = json.dumps(handshake_data, sort_keys=True).encode('utf-8')
        return self.verify_signature(message, handshake.signature, handshake.public_key)

    async def initiate_handshake(self, peer_url: str) -> tuple[PeerHandshake, PeerHandshake] | None:
        """
        Initiate handshake with a potential peer.

        Returns (our_handshake, their_handshake) if successful, None otherwise.
        """
        if not self._http_client:
            raise RuntimeError("Protocol not initialized")

        try:
            # Create our handshake
            our_handshake = await self.create_handshake()

            # Send to peer
            response = await self._http_client.post(
                f"{peer_url.rstrip('/')}/api/v1/federation/handshake",
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

        try:
            response = await self._http_client.get(
                f"{peer.url.rstrip('/')}/api/v1/federation/health",
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
                f"{peer.url.rstrip('/')}/api/v1/federation/changes",
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
                f"{peer.url.rstrip('/')}/api/v1/federation/incoming/capsules",
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
        """Verify a sync payload signature."""
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
        """Create a signed sync payload."""
        timestamp = datetime.now(timezone.utc)

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
        )

        # Sign the payload with empty signature field
        payload_json = payload.model_dump_json()
        payload.signature = self.sign_message(payload_json.encode('utf-8'))

        return payload
