"""
Password Hashing for Forge Cascade V2

Secure password hashing using bcrypt with configurable rounds.
Includes:
- Secure password hashing
- Timing-safe password verification
- Password strength validation
"""

import hmac
import re

import bcrypt

from ..config import get_settings

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
    except Exception:
        # On any error, still do a dummy comparison to maintain consistent timing
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
            return stored_rounds < _bcrypt_rounds
    except (ValueError, IndexError):
        pass
    return False


def get_password_strength(password: str) -> dict:
    """
    Evaluate password strength.

    Returns a dict with strength indicators.
    This is a simple implementation - consider using zxcvbn for production.
    """
    strength = {
        "length": len(password),
        "has_uppercase": any(c.isupper() for c in password),
        "has_lowercase": any(c.islower() for c in password),
        "has_digit": any(c.isdigit() for c in password),
        "has_special": any(not c.isalnum() for c in password),
        "score": 0,
        "feedback": []
    }

    # Calculate score (0-5)
    if strength["length"] >= 8:
        strength["score"] += 1
    if strength["length"] >= 12:
        strength["score"] += 1
    if strength["has_uppercase"]:
        strength["score"] += 1
    if strength["has_lowercase"]:
        strength["score"] += 1
    if strength["has_digit"]:
        strength["score"] += 1
    if strength["has_special"]:
        strength["score"] += 1

    # Generate feedback
    if strength["length"] < 8:
        strength["feedback"].append("Password should be at least 8 characters")
    if not strength["has_uppercase"]:
        strength["feedback"].append("Add uppercase letters")
    if not strength["has_lowercase"]:
        strength["feedback"].append("Add lowercase letters")
    if not strength["has_digit"]:
        strength["feedback"].append("Add numbers")
    if not strength["has_special"]:
        strength["feedback"].append("Add special characters for extra security")

    # Strength label
    if strength["score"] <= 2:
        strength["label"] = "weak"
    elif strength["score"] <= 4:
        strength["label"] = "moderate"
    else:
        strength["label"] = "strong"

    return strength
