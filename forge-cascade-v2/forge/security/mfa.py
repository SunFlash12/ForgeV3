"""
Multi-Factor Authentication (MFA) for Forge Cascade V2

SECURITY FIX (Audit 3): Implements TOTP-based MFA with:
- RFC 6238 compliant TOTP generation/verification
- Backup codes for account recovery
- Rate limiting on verification attempts
- Secure secret storage

Usage:
    mfa = MFAService()

    # Setup MFA for user
    secret, uri, backup_codes = await mfa.setup_mfa(user_id, user.email)
    # Show QR code from URI to user

    # Verify TOTP code during login
    if await mfa.verify_totp(user_id, code_from_user):
        # Allow login

    # Use backup code if TOTP unavailable
    if await mfa.verify_backup_code(user_id, backup_code):
        # Allow login, backup code is now consumed
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import quote

import structlog

logger = structlog.get_logger(__name__)

# TOTP Configuration
TOTP_DIGITS = 6
TOTP_PERIOD = 30  # seconds
TOTP_ALGORITHM = "sha1"
TOTP_ISSUER = "Forge Cascade"
TOTP_WINDOW = 1  # Allow codes from 1 period before/after for clock skew

# Backup codes configuration
BACKUP_CODE_COUNT = 10
BACKUP_CODE_LENGTH = 8

# Rate limiting
MAX_VERIFICATION_ATTEMPTS = 5
LOCKOUT_DURATION_SECONDS = 300  # 5 minutes


@dataclass
class MFAStatus:
    """MFA status for a user."""
    enabled: bool = False
    verified: bool = False  # Whether setup is complete
    created_at: Optional[datetime] = None
    last_used: Optional[datetime] = None
    backup_codes_remaining: int = 0


@dataclass
class MFASetupResult:
    """Result of MFA setup."""
    secret: str  # Base32 encoded secret
    provisioning_uri: str  # otpauth:// URI for QR code
    backup_codes: list[str]  # One-time backup codes


@dataclass
class VerificationAttempt:
    """Tracks verification attempts for rate limiting."""
    attempts: int = 0
    locked_until: Optional[datetime] = None


class MFAService:
    """
    Multi-Factor Authentication service using TOTP.

    Implements RFC 6238 (TOTP) with backup codes for recovery.

    SECURITY FIX (Audit 4): Added database persistence for MFA data.
    In-memory storage is now development-only with explicit warning.
    """

    def __init__(
        self,
        db_client=None,
        encryption_key: Optional[str] = None,
        use_memory_storage: bool = False,
    ):
        """
        Initialize MFA service.

        Args:
            db_client: Database client for persistent storage
            encryption_key: Key for encrypting secrets at rest (required for production)
            use_memory_storage: If True, use in-memory storage (DEV ONLY - data lost on restart!)
        """
        self._db = db_client
        self._encryption_key = encryption_key

        # SECURITY FIX (Audit 4): Warn if using memory storage in production
        if use_memory_storage or db_client is None:
            import os
            env = os.environ.get("FORGE_ENV", "development")
            if env != "development" and env != "test":
                logger.error(
                    "CRITICAL_SECURITY_WARNING",
                    message="MFA using in-memory storage in non-development environment!",
                    warning="MFA secrets will be LOST on restart. Users will be locked out.",
                    env=env,
                )
            else:
                logger.warning(
                    "mfa_memory_storage_warning",
                    message="MFA using in-memory storage - for development only",
                    warning="MFA secrets will be lost on restart",
                )
            self._use_db = False
        else:
            self._use_db = True
            if not encryption_key:
                logger.warning(
                    "mfa_encryption_warning",
                    message="MFA encryption key not provided - secrets stored unencrypted",
                )

        # In-memory fallback (DEV ONLY)
        self._secrets: dict[str, str] = {}  # user_id -> base32 secret
        self._backup_codes: dict[str, set[str]] = {}  # user_id -> set of hashed codes
        self._verified: dict[str, bool] = {}  # user_id -> whether MFA setup is verified
        self._last_used: dict[str, datetime] = {}  # user_id -> last MFA use time
        self._verification_attempts: dict[str, VerificationAttempt] = {}

        logger.info(
            "MFA service initialized",
            storage="database" if self._use_db else "memory",
            encrypted=bool(encryption_key),
        )

    def _encrypt_secret(self, secret: str) -> str:
        """Encrypt a secret for storage."""
        if not self._encryption_key:
            return secret
        # Simple encryption using Fernet (production should use HSM)
        try:
            from cryptography.fernet import Fernet
            import base64
            # Derive a valid Fernet key from the encryption key
            key = base64.urlsafe_b64encode(
                hashlib.sha256(self._encryption_key.encode()).digest()
            )
            f = Fernet(key)
            return f.encrypt(secret.encode()).decode()
        except ImportError:
            logger.warning("cryptography not installed, storing unencrypted")
            return secret

    def _decrypt_secret(self, encrypted: str) -> str:
        """Decrypt a stored secret."""
        if not self._encryption_key:
            return encrypted
        try:
            from cryptography.fernet import Fernet
            import base64
            key = base64.urlsafe_b64encode(
                hashlib.sha256(self._encryption_key.encode()).digest()
            )
            f = Fernet(key)
            return f.decrypt(encrypted.encode()).decode()
        except ImportError:
            return encrypted
        except Exception as e:
            logger.error("mfa_decrypt_error", error=str(e))
            raise ValueError("Failed to decrypt MFA secret")

    async def _persist_mfa_data(
        self,
        user_id: str,
        secret: str,
        backup_codes_hashed: set[str],
        verified: bool,
    ) -> None:
        """Persist MFA data to database."""
        if not self._use_db:
            return

        encrypted_secret = self._encrypt_secret(secret)
        mfa_data = {
            "user_id": user_id,
            "secret_encrypted": encrypted_secret,
            "backup_codes_hashed": list(backup_codes_hashed),
            "verified": verified,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_used": None,
        }

        # Store in database
        async with self._db.session() as session:
            await session.run(
                """
                MERGE (m:MFACredential {user_id: $user_id})
                SET m.secret_encrypted = $secret_encrypted,
                    m.backup_codes_hashed = $backup_codes_hashed,
                    m.verified = $verified,
                    m.created_at = $created_at,
                    m.updated_at = datetime()
                """,
                mfa_data
            )
        logger.info("mfa_data_persisted", user_id=user_id)

    async def _load_mfa_data(self, user_id: str) -> Optional[dict]:
        """Load MFA data from database."""
        if not self._use_db:
            return None

        async with self._db.session() as session:
            result = await session.run(
                """
                MATCH (m:MFACredential {user_id: $user_id})
                RETURN m {.*} AS mfa
                """,
                {"user_id": user_id}
            )
            record = await result.single()
            if record:
                return dict(record["mfa"])
        return None

    # =========================================================================
    # Setup
    # =========================================================================

    def generate_secret(self) -> str:
        """
        Generate a cryptographically secure random secret.

        Returns:
            Base32-encoded secret (160 bits of entropy)
        """
        # Generate 20 random bytes (160 bits) as recommended by RFC 4226
        random_bytes = secrets.token_bytes(20)
        return base64.b32encode(random_bytes).decode("ascii")

    def generate_backup_codes(self, count: int = BACKUP_CODE_COUNT) -> list[str]:
        """
        Generate one-time backup codes.

        Args:
            count: Number of codes to generate

        Returns:
            List of plaintext backup codes (store hashes, show user once)
        """
        codes = []
        for _ in range(count):
            # Generate random alphanumeric code (easy to type)
            code = secrets.token_hex(BACKUP_CODE_LENGTH // 2).upper()
            # Format as XXXX-XXXX for readability
            formatted = f"{code[:4]}-{code[4:]}"
            codes.append(formatted)
        return codes

    def _hash_backup_code(self, code: str) -> str:
        """Hash a backup code for secure storage."""
        # Normalize: remove dashes, uppercase
        normalized = code.replace("-", "").upper()
        return hashlib.sha256(normalized.encode()).hexdigest()

    async def setup_mfa(self, user_id: str, email: str) -> MFASetupResult:
        """
        Initialize MFA setup for a user.

        Args:
            user_id: User's ID
            email: User's email (for TOTP label)

        Returns:
            MFASetupResult with secret, URI, and backup codes
        """
        # Generate new secret
        secret = self.generate_secret()

        # Generate backup codes
        backup_codes = self.generate_backup_codes()

        # Hash backup codes for storage
        hashed_codes = {
            self._hash_backup_code(code) for code in backup_codes
        }

        # Store in memory (for immediate use)
        self._secrets[user_id] = secret
        self._verified[user_id] = False
        self._backup_codes[user_id] = hashed_codes

        # SECURITY FIX (Audit 4): Persist to database
        await self._persist_mfa_data(
            user_id=user_id,
            secret=secret,
            backup_codes_hashed=hashed_codes,
            verified=False,
        )

        # Generate provisioning URI for QR code
        uri = self._generate_provisioning_uri(secret, email)

        logger.info(
            "MFA setup initiated",
            user_id=user_id,
            backup_codes_count=len(backup_codes),
            persisted=self._use_db,
        )

        return MFASetupResult(
            secret=secret,
            provisioning_uri=uri,
            backup_codes=backup_codes
        )

    def _generate_provisioning_uri(self, secret: str, email: str) -> str:
        """
        Generate otpauth:// URI for TOTP authenticator apps.

        Format: otpauth://totp/ISSUER:ACCOUNT?secret=SECRET&issuer=ISSUER&algorithm=SHA1&digits=6&period=30
        """
        label = f"{TOTP_ISSUER}:{email}"
        params = {
            "secret": secret,
            "issuer": TOTP_ISSUER,
            "algorithm": TOTP_ALGORITHM.upper(),
            "digits": str(TOTP_DIGITS),
            "period": str(TOTP_PERIOD),
        }

        query = "&".join(f"{k}={quote(v)}" for k, v in params.items())
        return f"otpauth://totp/{quote(label)}?{query}"

    async def verify_setup(self, user_id: str, code: str) -> bool:
        """
        Verify MFA setup by checking a TOTP code.

        This must be called after setup to confirm the user has correctly
        configured their authenticator app.

        Args:
            user_id: User's ID
            code: TOTP code from authenticator

        Returns:
            True if code is valid and setup is now complete
        """
        if user_id not in self._secrets:
            logger.warning("MFA verify_setup called for user without pending setup", user_id=user_id)
            return False

        if await self.verify_totp(user_id, code, skip_verified_check=True):
            self._verified[user_id] = True
            self._last_used[user_id] = datetime.now(timezone.utc)

            logger.info("MFA setup verified", user_id=user_id)
            return True

        return False

    # =========================================================================
    # Verification
    # =========================================================================

    def _generate_totp(self, secret: str, timestamp: Optional[int] = None) -> str:
        """
        Generate TOTP code for a given timestamp.

        Implements RFC 6238 TOTP algorithm.

        Args:
            secret: Base32-encoded secret
            timestamp: Unix timestamp (defaults to current time)

        Returns:
            6-digit TOTP code
        """
        if timestamp is None:
            timestamp = int(time.time())

        # Calculate time counter (T)
        counter = timestamp // TOTP_PERIOD

        # Decode secret
        try:
            key = base64.b32decode(secret, casefold=True)
        except Exception:
            return ""

        # Generate HMAC-SHA1 of counter
        counter_bytes = struct.pack(">Q", counter)
        hmac_hash = hmac.new(key, counter_bytes, hashlib.sha1).digest()

        # Dynamic truncation
        offset = hmac_hash[-1] & 0x0F
        truncated = struct.unpack(">I", hmac_hash[offset:offset + 4])[0]
        truncated &= 0x7FFFFFFF  # Clear most significant bit

        # Generate code
        code = truncated % (10 ** TOTP_DIGITS)
        return str(code).zfill(TOTP_DIGITS)

    def _check_rate_limit(self, user_id: str) -> tuple[bool, Optional[str]]:
        """
        Check if user is rate limited.

        Returns:
            Tuple of (is_allowed, error_message)
        """
        attempt = self._verification_attempts.get(user_id)

        if attempt is None:
            return True, None

        # Check if locked
        if attempt.locked_until:
            if datetime.now(timezone.utc) < attempt.locked_until:
                remaining = (attempt.locked_until - datetime.now(timezone.utc)).seconds
                return False, f"Too many failed attempts. Try again in {remaining} seconds."
            else:
                # Lockout expired, reset
                self._verification_attempts[user_id] = VerificationAttempt()
                return True, None

        return True, None

    def _record_attempt(self, user_id: str, success: bool) -> None:
        """Record a verification attempt for rate limiting."""
        if user_id not in self._verification_attempts:
            self._verification_attempts[user_id] = VerificationAttempt()

        attempt = self._verification_attempts[user_id]

        if success:
            # Reset on success
            attempt.attempts = 0
            attempt.locked_until = None
        else:
            attempt.attempts += 1

            if attempt.attempts >= MAX_VERIFICATION_ATTEMPTS:
                # SECURITY FIX (Audit 4 - M3): Correct lockout time calculation
                # Previous code used .replace(second=...) which overflows incorrectly
                attempt.locked_until = datetime.now(timezone.utc) + timedelta(
                    seconds=LOCKOUT_DURATION_SECONDS
                )
                logger.warning(
                    "MFA verification locked",
                    user_id=user_id,
                    attempts=attempt.attempts,
                    locked_until=attempt.locked_until.isoformat(),
                )

    async def _ensure_loaded(self, user_id: str) -> bool:
        """
        SECURITY FIX (Audit 4): Ensure MFA data is loaded from database.

        Returns:
            True if data is available (from memory or loaded from DB)
        """
        if user_id in self._secrets:
            return True

        # Try to load from database
        mfa_data = await self._load_mfa_data(user_id)
        if mfa_data:
            try:
                encrypted = mfa_data.get("secret_encrypted", "")
                self._secrets[user_id] = self._decrypt_secret(encrypted)
                self._verified[user_id] = mfa_data.get("verified", False)
                self._backup_codes[user_id] = set(mfa_data.get("backup_codes_hashed", []))
                if mfa_data.get("last_used"):
                    self._last_used[user_id] = datetime.fromisoformat(mfa_data["last_used"])
                logger.info("mfa_data_loaded_from_db", user_id=user_id)
                return True
            except Exception as e:
                logger.error("mfa_data_load_error", user_id=user_id, error=str(e))
                return False

        return False

    async def verify_totp(
        self,
        user_id: str,
        code: str,
        skip_verified_check: bool = False
    ) -> bool:
        """
        Verify a TOTP code.

        Args:
            user_id: User's ID
            code: 6-digit TOTP code
            skip_verified_check: If True, allow verification during setup

        Returns:
            True if code is valid
        """
        # Rate limiting
        allowed, error = self._check_rate_limit(user_id)
        if not allowed:
            logger.warning("MFA verification rate limited", user_id=user_id, error=error)
            return False

        # SECURITY FIX (Audit 4): Load from database if not in memory
        await self._ensure_loaded(user_id)

        # Check if MFA is set up
        secret = self._secrets.get(user_id)
        if not secret:
            logger.warning("MFA verification for user without MFA", user_id=user_id)
            return False

        # Check if setup is verified (unless we're verifying setup)
        if not skip_verified_check and not self._verified.get(user_id, False):
            logger.warning("MFA verification for unverified setup", user_id=user_id)
            return False

        # Validate code format
        if not code or len(code) != TOTP_DIGITS or not code.isdigit():
            self._record_attempt(user_id, False)
            return False

        # Check current and adjacent time windows (for clock skew)
        current_time = int(time.time())

        for offset in range(-TOTP_WINDOW, TOTP_WINDOW + 1):
            check_time = current_time + (offset * TOTP_PERIOD)
            expected_code = self._generate_totp(secret, check_time)

            # Constant-time comparison to prevent timing attacks
            if hmac.compare_digest(code, expected_code):
                self._record_attempt(user_id, True)
                self._last_used[user_id] = datetime.now(timezone.utc)

                logger.info("MFA TOTP verified", user_id=user_id)
                return True

        self._record_attempt(user_id, False)
        logger.warning("MFA TOTP verification failed", user_id=user_id)
        return False

    async def verify_backup_code(self, user_id: str, code: str) -> bool:
        """
        Verify and consume a backup code.

        Backup codes are one-time use and are removed after successful verification.

        Args:
            user_id: User's ID
            code: Backup code

        Returns:
            True if code is valid (code is now consumed)
        """
        # Rate limiting
        allowed, error = self._check_rate_limit(user_id)
        if not allowed:
            logger.warning("MFA backup code rate limited", user_id=user_id, error=error)
            return False

        codes = self._backup_codes.get(user_id)
        if not codes:
            logger.warning("MFA backup code for user without codes", user_id=user_id)
            return False

        # Hash the provided code
        code_hash = self._hash_backup_code(code)

        if code_hash in codes:
            # Remove the used code (one-time use)
            codes.remove(code_hash)
            self._record_attempt(user_id, True)
            self._last_used[user_id] = datetime.now(timezone.utc)

            logger.info(
                "MFA backup code used",
                user_id=user_id,
                remaining_codes=len(codes)
            )
            return True

        self._record_attempt(user_id, False)
        logger.warning("MFA backup code verification failed", user_id=user_id)
        return False

    # =========================================================================
    # Management
    # =========================================================================

    async def get_status(self, user_id: str) -> MFAStatus:
        """Get MFA status for a user."""
        if user_id not in self._secrets:
            return MFAStatus(enabled=False)

        return MFAStatus(
            enabled=True,
            verified=self._verified.get(user_id, False),
            last_used=self._last_used.get(user_id),
            backup_codes_remaining=len(self._backup_codes.get(user_id, set()))
        )

    async def is_enabled(self, user_id: str) -> bool:
        """Check if MFA is enabled and verified for a user."""
        return (
            user_id in self._secrets and
            self._verified.get(user_id, False)
        )

    async def disable_mfa(self, user_id: str) -> bool:
        """
        Disable MFA for a user.

        Args:
            user_id: User's ID

        Returns:
            True if MFA was disabled
        """
        if user_id not in self._secrets:
            return False

        # Remove all MFA data
        self._secrets.pop(user_id, None)
        self._backup_codes.pop(user_id, None)
        self._verified.pop(user_id, None)
        self._last_used.pop(user_id, None)
        self._verification_attempts.pop(user_id, None)

        logger.info("MFA disabled", user_id=user_id)
        return True

    async def regenerate_backup_codes(self, user_id: str) -> list[str]:
        """
        Regenerate backup codes for a user.

        This invalidates all previous backup codes.

        Args:
            user_id: User's ID

        Returns:
            New list of backup codes

        Raises:
            ValueError: If MFA is not enabled for user
        """
        if user_id not in self._secrets:
            raise ValueError("MFA is not enabled for this user")

        # Generate new codes
        backup_codes = self.generate_backup_codes()

        # Replace stored codes
        self._backup_codes[user_id] = {
            self._hash_backup_code(code) for code in backup_codes
        }

        logger.info(
            "MFA backup codes regenerated",
            user_id=user_id,
            count=len(backup_codes)
        )

        return backup_codes


# Singleton instance
_mfa_service: Optional[MFAService] = None


def get_mfa_service() -> MFAService:
    """Get or create the MFA service singleton."""
    global _mfa_service
    if _mfa_service is None:
        _mfa_service = MFAService()
    return _mfa_service
