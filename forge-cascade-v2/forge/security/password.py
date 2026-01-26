"""
Password Hashing for Forge Cascade V2

Secure password hashing using bcrypt with configurable rounds.
Includes:
- Secure password hashing
- Timing-safe password verification
- Password strength validation
- Entropy-based validation with zxcvbn (optional)
"""

import hmac
import re
from collections.abc import Callable
from typing import Any

import bcrypt
import structlog

from ..config import get_settings

logger = structlog.get_logger(__name__)

# SECURITY FIX (Audit 5): Optional zxcvbn integration for entropy-based validation
zxcvbn_check: Callable[[str, list[str] | None], Any] | None
try:
    from zxcvbn import zxcvbn as zxcvbn_check
    ZXCVBN_AVAILABLE = True
except ImportError:
    zxcvbn_check = None
    ZXCVBN_AVAILABLE = False
    logger.info("zxcvbn not installed - using pattern-based password validation only")

settings = get_settings()

# Get bcrypt rounds from settings
_bcrypt_rounds = settings.password_bcrypt_rounds

# Password strength requirements
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128

# SECURITY FIX (Audit 2 + 3): Comprehensive common weak passwords blacklist
# Top 200+ most common passwords from breach databases
#
# SECURITY NOTE (Audit 4 - L9): For enhanced protection, consider integrating
# with the HaveIBeenPwned API using the k-anonymity model:
# https://haveibeenpwned.com/API/v3#PwnedPasswords
# This would check against billions of breached passwords without exposing the password.
COMMON_WEAK_PASSWORDS = frozenset({
    # Original list
    "password", "password1", "password123", "password!",
    "12345678", "123456789", "1234567890",
    "qwerty123", "qwertyuiop", "qwerty1234",
    "letmein1", "welcome1", "admin123", "admin1234",
    "iloveyou1", "sunshine1", "princess1",
    "football1", "baseball1", "dragon123",
    "master123", "monkey123", "shadow123",
    "abc12345", "abcd1234", "abcdefgh",
    "passw0rd", "p@ssw0rd", "p@ssword",
    "changeme", "changeme1", "temp1234",
    # SECURITY FIX (Audit 3): Extended common password list
    # Top breach passwords
    "password12", "password2", "password3",
    "12345678!", "qwerty12", "letmein!", "welcome!", "welcome12",
    "iloveyou", "iloveyou!", "trustno1", "trustno1!",
    "1qaz2wsx", "1q2w3e4r", "1q2w3e4r5t", "zaq12wsx",
    "!qaz2wsx", "qazwsx123", "1qazxsw2",
    # Simple words with numbers
    "dragon12", "michael1", "jennifer1", "jordan23",
    "mustang1", "hunter12", "summer12", "winter12",
    "charlie1", "yankees1", "rangers1", "cowboys1",
    "superman1", "batman123", "spiderman1",
    # Keyboard patterns
    "asdfghjkl", "zxcvbnm1", "asdf1234", "qweasdzxc",
    "asdfqwer", "1234qwer", "qwer1234!", "asdf!234",
    # Common with substitutions
    "p4ssw0rd", "passw0rd!", "pa$$word", "pa$$w0rd",
    "l3tm31n", "w3lc0me", "adm1n123", "r00tpass",
    # Year-based
    "password2020", "password2021", "password2022", "password2023",
    "password2024", "password2025", "qwerty2020", "qwerty2021",
    "summer2020", "summer2021", "winter2020", "winter2021",
    # Company/service patterns (will also check dynamically)
    "admin1234!", "root1234", "test1234", "guest1234",
    "demo1234", "user1234", "login1234", "access123",
    # Sports teams and names
    "yankees123", "cowboys123", "lakers123", "steelers1",
    "patriots1", "eagles123", "broncos123", "giants123",
    # Popular names with numbers
    "michael123", "jennifer12", "jessica123", "ashley123",
    "matthew123", "andrew123", "joshua123", "daniel123",
    # More keyboard patterns
    "qwertyui", "asdfghjk", "zxcvbnm!", "!qazxsw2",
    "1234abcd", "abcd!234", "aaaa1111", "1111aaaa",
    # Love/emotion patterns
    "iloveu123", "loveyou12", "mylove123",
    "babe1234", "honey1234", "sweetie1", "darling1",
    # Tech patterns
    "computer1", "internet1", "windows10", "apple123",
    "google123", "facebook1", "twitter1", "instagram1",
    # Animal patterns
    "tiger1234", "lion12345",
    "bear12345", "wolf12345", "eagle1234", "shark1234",
})

# SECURITY FIX (Audit 3): Context-aware banned substrings
BANNED_PASSWORD_SUBSTRINGS = frozenset({
    "forge", "cascade", "admin", "root", "test", "demo",
    "user", "pass", "login", "guest", "temp", "default",
})


class PasswordValidationError(Exception):
    """Password does not meet requirements."""
    pass


def validate_password_strength(password: str, username: str | None = None, email: str | None = None) -> None:
    """
    Validate password meets minimum security requirements.

    Backend enforcement of password policy.

    Args:
        password: Password to validate
        username: Optional username to check password doesn't contain it
        email: Optional email to check password doesn't contain it

    Raises:
        PasswordValidationError: If password doesn't meet requirements
    """
    if len(password) < PASSWORD_MIN_LENGTH:
        raise PasswordValidationError(f"Password must be at least {PASSWORD_MIN_LENGTH} characters")

    if len(password) > PASSWORD_MAX_LENGTH:
        raise PasswordValidationError(f"Password cannot exceed {PASSWORD_MAX_LENGTH} characters")

    if not any(c.isupper() for c in password):
        raise PasswordValidationError("Password must contain at least one uppercase letter")

    if not any(c.islower() for c in password):
        raise PasswordValidationError("Password must contain at least one lowercase letter")

    if not any(c.isdigit() for c in password):
        raise PasswordValidationError("Password must contain at least one digit")

    # SECURITY FIX (Audit 2): Require at least one special character
    if not any(not c.isalnum() for c in password):
        raise PasswordValidationError("Password must contain at least one special character")

    # SECURITY FIX (Audit 2): Check against common weak passwords blacklist
    password_lower = password.lower()
    if password_lower in COMMON_WEAK_PASSWORDS:
        raise PasswordValidationError("Password is too common and easily guessable")

    # SECURITY FIX (Audit 3): Check for banned substrings (service/product names)
    for banned in BANNED_PASSWORD_SUBSTRINGS:
        if banned in password_lower:
            raise PasswordValidationError("Password cannot contain common words like 'admin', 'password', or service names")

    # SECURITY FIX (Audit 3): Context-aware validation - check username similarity
    if username:
        username_lower = username.lower()
        # Check if password contains username
        if username_lower in password_lower:
            raise PasswordValidationError("Password cannot contain your username")
        # Check if username contains password (reversed case)
        if len(username_lower) >= 4 and password_lower in username_lower:
            raise PasswordValidationError("Password is too similar to your username")
        # Check for common variations (username123, username!, etc.)
        if password_lower.startswith(username_lower) or password_lower.endswith(username_lower):
            raise PasswordValidationError("Password cannot be based on your username")

    # SECURITY FIX (Audit 3): Context-aware validation - check email similarity
    if email:
        email_lower = email.lower()
        email_local = email_lower.split("@")[0] if "@" in email_lower else email_lower
        if len(email_local) >= 4 and email_local in password_lower:
            raise PasswordValidationError("Password cannot contain your email address")

    # Check for common weak patterns
    common_patterns = [
        r'^(.)\1+$',  # All same character
        r'^(012|123|234|345|456|567|678|789|890)+',  # Sequential numbers
        r'^(abc|bcd|cde|def|efg|fgh|ghi|hij|ijk|jkl|klm|lmn|mno|nop|opq|pqr|qrs|rst|stu|tuv|uvw|vwx|wxy|xyz)+',  # Sequential letters
    ]
    for pattern in common_patterns:
        if re.match(pattern, password_lower):
            raise PasswordValidationError("Password contains a weak pattern")

    # SECURITY FIX (Audit 3): Check for repeated character patterns
    if _has_repeated_pattern(password_lower):
        raise PasswordValidationError("Password contains a repetitive pattern")

    # SECURITY FIX (Audit 5): Entropy-based validation with zxcvbn
    if ZXCVBN_AVAILABLE and zxcvbn_check is not None:
        user_inputs = []
        if username:
            user_inputs.append(username)
        if email:
            user_inputs.append(email)
            # Also add email local part
            if "@" in email:
                user_inputs.append(email.split("@")[0])

        result = zxcvbn_check(password, user_inputs)
        # zxcvbn score: 0=very weak, 1=weak, 2=fair, 3=strong, 4=very strong
        # Require minimum score of 2 (fair)
        if result["score"] < 2:
            feedback = result.get("feedback", {})
            warning = feedback.get("warning", "")
            suggestions = feedback.get("suggestions", [])

            # Build helpful error message
            error_parts = ["Password is too weak"]
            if warning:
                error_parts.append(f": {warning}")
            if suggestions:
                error_parts.append(f". Suggestions: {'; '.join(suggestions[:2])}")

            raise PasswordValidationError("".join(error_parts))


def _has_repeated_pattern(password: str) -> bool:
    """
    Check if password has a simple repeated pattern like 'abcabc' or 'abab'.

    SECURITY FIX (Audit 3): Detect repetitive patterns that reduce entropy.
    """
    length = len(password)
    # Check for patterns of length 2-4 repeated
    for pattern_len in range(2, min(5, length // 2 + 1)):
        pattern = password[:pattern_len]
        # Check if entire password is just this pattern repeated
        if pattern * (length // pattern_len) == password[:pattern_len * (length // pattern_len)]:
            # At least 3 repetitions to be considered weak
            if length // pattern_len >= 3:
                return True
    return False


def hash_password(
    password: str,
    validate: bool = True,
    username: str | None = None,
    email: str | None = None
) -> str:
    """
    Hash a password using bcrypt.

    Args:
        password: Plain text password
        validate: Whether to validate password strength (default True)
        username: Optional username for context-aware validation
        email: Optional email for context-aware validation

    Returns:
        Bcrypt hash of the password

    Raises:
        PasswordValidationError: If password doesn't meet requirements
    """
    if validate:
        validate_password_strength(password, username=username, email=email)

    # SECURITY FIX (Audit 4 - L10): Apply Unicode NFKC normalization before hashing
    # This ensures consistent hashing regardless of Unicode representation variants
    # (e.g., é as single char vs e + combining accent)
    import unicodedata
    normalized_password = unicodedata.normalize('NFKC', password)
    password_bytes = normalized_password.encode('utf-8')
    salt = bcrypt.gensalt(rounds=_bcrypt_rounds)
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash using timing-safe comparison.

    Uses bcrypt's built-in constant-time comparison to prevent timing attacks.

    Args:
        plain_password: Plain text password to verify
        hashed_password: Bcrypt hash to verify against

    Returns:
        True if password matches, False otherwise
    """
    if not plain_password or not hashed_password:
        # Use constant-time comparison even for empty inputs
        # to prevent timing-based detection of which input was empty
        hmac.compare_digest("dummy", "dummy")
        return False

    try:
        # SECURITY FIX (Audit 4 - L10): Apply same Unicode normalization as hash_password
        import unicodedata
        normalized_password = unicodedata.normalize('NFKC', plain_password)

        # bcrypt.checkpw is designed to be constant-time
        result = bcrypt.checkpw(
            normalized_password.encode('utf-8'),
            hashed_password.encode('utf-8')
        )
        return result
    except (ValueError, TypeError) as e:
        # Intentional broad catch: maintain consistent timing on any bcrypt/encoding error
        _ = e  # Logged at debug level only to avoid timing side-channels
        hmac.compare_digest("dummy", "dummy")
        return False


def needs_rehash(hashed_password: str) -> bool:
    """
    Check if a password hash needs to be rehashed.

    This can happen if the number of bcrypt rounds has been increased
    since the password was originally hashed.

    Args:
        hashed_password: Existing hash to check

    Returns:
        True if password should be rehashed with current settings
    """
    try:
        # Extract rounds from the hash (format: $2b$XX$...)
        parts = hashed_password.split('$')
        if len(parts) >= 3:
            stored_rounds = int(parts[2])
            result: bool = stored_rounds < _bcrypt_rounds
            return result
    except (ValueError, IndexError):
        pass
    return False


def check_password_history(
    new_password: str,
    password_history: list[str],
    history_count: int | None = None
) -> bool:
    """
    SECURITY FIX (Audit 6): Check if a password was recently used.

    Prevents password reuse by checking against stored password history.
    Uses constant-time comparison for each check to prevent timing attacks.

    Args:
        new_password: The new password to check
        password_history: List of previous password hashes (most recent first)
        history_count: Number of previous passwords to check (from settings if None)

    Returns:
        True if password matches any in history (reused), False if new

    Raises:
        PasswordValidationError: If password was recently used
    """
    if not password_history:
        return False

    # Get history count from settings if not specified
    if history_count is None:
        history_count = settings.password_history_count

    # Only check up to history_count passwords
    passwords_to_check = password_history[:history_count]

    # Apply same normalization as verify_password
    import unicodedata
    normalized_password = unicodedata.normalize('NFKC', new_password)

    for old_hash in passwords_to_check:
        try:
            if bcrypt.checkpw(
                normalized_password.encode('utf-8'),
                old_hash.encode('utf-8')
            ):
                logger.warning(
                    "password_reuse_detected",
                    history_position=passwords_to_check.index(old_hash) + 1,
                )
                raise PasswordValidationError(
                    f"Password was used recently. Please choose a password you haven't used in the last {history_count} password changes."
                )
        except PasswordValidationError:
            raise
        except (ValueError, TypeError):
            # Skip invalid hashes but continue checking
            continue

    return False


def update_password_history(
    current_hash: str,
    password_history: list[str],
    max_history: int | None = None
) -> list[str]:
    """
    SECURITY FIX (Audit 6): Update password history with new hash.

    Prepends the current password hash to history and trims to max size.

    Args:
        current_hash: The current password hash to add to history
        password_history: Existing password history list
        max_history: Maximum passwords to retain (from settings if None)

    Returns:
        Updated password history list (new list, doesn't modify original)
    """
    if max_history is None:
        max_history = settings.password_history_count

    # Create new list with current hash at front
    new_history = [current_hash] + (password_history or [])

    # Trim to max size
    return new_history[:max_history]


def get_password_strength(password: str, username: str | None = None, email: str | None = None) -> dict[str, Any]:
    """
    Evaluate password strength.

    SECURITY FIX (Audit 5): Now uses zxcvbn when available for true entropy-based
    strength evaluation. Falls back to pattern-based evaluation if zxcvbn unavailable.

    Args:
        password: Password to evaluate
        username: Optional username for context-aware evaluation
        email: Optional email for context-aware evaluation

    Returns:
        Dict with strength indicators including score, label, and feedback
    """
    # SECURITY FIX (Audit 5): Use zxcvbn for accurate entropy-based evaluation
    if ZXCVBN_AVAILABLE and zxcvbn_check is not None:
        user_inputs = []
        if username:
            user_inputs.append(username)
        if email:
            user_inputs.append(email)
            if "@" in email:
                user_inputs.append(email.split("@")[0])

        result = zxcvbn_check(password, user_inputs)
        feedback_obj = result.get("feedback", {})

        # Map zxcvbn score (0-4) to labels
        score_labels = {
            0: "very_weak",
            1: "weak",
            2: "fair",
            3: "strong",
            4: "very_strong"
        }

        return {
            "length": len(password),
            "has_uppercase": any(c.isupper() for c in password),
            "has_lowercase": any(c.islower() for c in password),
            "has_digit": any(c.isdigit() for c in password),
            "has_special": any(not c.isalnum() for c in password),
            "score": result["score"],
            "label": score_labels.get(result["score"], "unknown"),
            "feedback": feedback_obj.get("suggestions", []),
            "warning": feedback_obj.get("warning", ""),
            "crack_time_display": result.get("crack_times_display", {}).get("offline_slow_hashing_1e4_per_second", ""),
            "entropy_based": True,
        }

    # Fallback: Pattern-based evaluation
    length: int = len(password)
    has_uppercase: bool = any(c.isupper() for c in password)
    has_lowercase: bool = any(c.islower() for c in password)
    has_digit: bool = any(c.isdigit() for c in password)
    has_special: bool = any(not c.isalnum() for c in password)
    score: int = 0
    feedback: list[str] = []

    # Calculate score (0-5)
    if length >= 8:
        score += 1
    if length >= 12:
        score += 1
    if has_uppercase:
        score += 1
    if has_lowercase:
        score += 1
    if has_digit:
        score += 1
    if has_special:
        score += 1

    # Generate feedback
    if length < 8:
        feedback.append("Password should be at least 8 characters")
    if not has_uppercase:
        feedback.append("Add uppercase letters")
    if not has_lowercase:
        feedback.append("Add lowercase letters")
    if not has_digit:
        feedback.append("Add numbers")
    if not has_special:
        feedback.append("Add special characters for extra security")

    # Strength label (map 0-6 score to labels)
    label: str
    if score <= 2:
        label = "weak"
    elif score <= 4:
        label = "moderate"
    else:
        label = "strong"

    strength: dict[str, Any] = {
        "length": length,
        "has_uppercase": has_uppercase,
        "has_lowercase": has_lowercase,
        "has_digit": has_digit,
        "has_special": has_special,
        "score": score,
        "feedback": feedback,
        "entropy_based": False,
        "label": label,
    }

    return strength
