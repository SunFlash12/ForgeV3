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


class PasswordValidationError(Exception):
    """Password does not meet requirements."""
    pass


def validate_password_strength(password: str) -> None:
    """
    Validate password meets minimum security requirements.

    Backend enforcement of password policy.

    Args:
        password: Password to validate

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

    # Check for common weak patterns
    common_patterns = [
        r'^(.)\1+$',  # All same character
        r'^(012|123|234|345|456|567|678|789|890)+',  # Sequential numbers
        r'^(abc|bcd|cde|def|efg|fgh|ghi|hij|ijk|jkl|klm|lmn|mno|nop|opq|pqr|qrs|rst|stu|tuv|uvw|vwx|wxy|xyz)+',  # Sequential letters
    ]
    for pattern in common_patterns:
        if re.match(pattern, password.lower()):
            raise PasswordValidationError("Password contains a weak pattern")


def hash_password(password: str, validate: bool = True) -> str:
    """
    Hash a password using bcrypt.

    Args:
        password: Plain text password
        validate: Whether to validate password strength (default True)

    Returns:
        Bcrypt hash of the password

    Raises:
        PasswordValidationError: If password doesn't meet requirements
    """
    if validate:
        validate_password_strength(password)

    password_bytes = password.encode('utf-8')
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
        # bcrypt.checkpw is designed to be constant-time
        result = bcrypt.checkpw(
            plain_password.encode('utf-8'),
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
