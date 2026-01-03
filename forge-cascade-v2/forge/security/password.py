"""
Password Hashing for Forge Cascade V2

Secure password hashing using bcrypt with configurable rounds.
"""

from passlib.context import CryptContext

from ..config import get_settings

settings = get_settings()

# Configure bcrypt context
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=settings.password_bcrypt_rounds
)


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.
    
    Args:
        password: Plain text password
        
    Returns:
        Bcrypt hash of the password
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.
    
    Args:
        plain_password: Plain text password to verify
        hashed_password: Bcrypt hash to verify against
        
    Returns:
        True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


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
    return pwd_context.needs_update(hashed_password)


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
