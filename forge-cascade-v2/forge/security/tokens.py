"""
JWT Token Management for Forge Cascade V2

Handles creation, validation, and refresh of JWT tokens
for user authentication.
"""

from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import uuid4

from jose import JWTError, jwt
from pydantic import ValidationError

from ..config import get_settings
from ..models.user import TokenPayload, Token

settings = get_settings()


class TokenError(Exception):
    """Base exception for token-related errors."""
    pass


class TokenExpiredError(TokenError):
    """Token has expired."""
    pass


class TokenInvalidError(TokenError):
    """Token is invalid or malformed."""
    pass


def create_access_token(
    user_id: str,
    username: str,
    role: str,
    trust_flame: int,
    additional_claims: Optional[dict[str, Any]] = None
) -> str:
    """
    Create a JWT access token.
    
    Args:
        user_id: User's unique identifier
        username: User's username
        role: User's role (user, moderator, admin, system)
        trust_flame: User's trust score (0-100)
        additional_claims: Extra claims to include in token
        
    Returns:
        Encoded JWT access token
    """
    expire = datetime.utcnow() + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "trust_flame": trust_flame,
        "exp": expire,
        "iat": datetime.utcnow(),
        "jti": str(uuid4()),  # JWT ID for token revocation
        "type": "access"
    }
    
    if additional_claims:
        payload.update(additional_claims)
    
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(
    user_id: str,
    username: str
) -> str:
    """
    Create a JWT refresh token.
    
    Refresh tokens have longer expiration and are used to get new access tokens.
    
    Args:
        user_id: User's unique identifier
        username: User's username
        
    Returns:
        Encoded JWT refresh token
    """
    expire = datetime.utcnow() + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    
    payload = {
        "sub": user_id,
        "username": username,
        "exp": expire,
        "iat": datetime.utcnow(),
        "jti": str(uuid4()),
        "type": "refresh"
    }
    
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_token_pair(
    user_id: str,
    username: str,
    role: str,
    trust_flame: int
) -> Token:
    """
    Create both access and refresh tokens.
    
    Args:
        user_id: User's unique identifier
        username: User's username
        role: User's role
        trust_flame: User's trust score
        
    Returns:
        Token model with both access and refresh tokens
    """
    access_token = create_access_token(user_id, username, role, trust_flame)
    refresh_token = create_refresh_token(user_id, username)
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60  # Convert to seconds
    )


def decode_token(token: str, verify_exp: bool = True) -> TokenPayload:
    """
    Decode and validate a JWT token.
    
    Args:
        token: JWT token string
        verify_exp: Whether to verify expiration (default True)
        
    Returns:
        TokenPayload with decoded claims
        
    Raises:
        TokenExpiredError: If token has expired
        TokenInvalidError: If token is invalid
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"verify_exp": verify_exp}
        )
        
        return TokenPayload(
            sub=payload["sub"],
            username=payload.get("username"),
            role=payload.get("role"),
            trust_flame=payload.get("trust_flame"),
            exp=payload.get("exp"),
            iat=payload.get("iat"),
            type=payload.get("type", "access")
        )
        
    except jwt.ExpiredSignatureError:
        raise TokenExpiredError("Token has expired")
    except JWTError as e:
        raise TokenInvalidError(f"Invalid token: {str(e)}")
    except ValidationError as e:
        raise TokenInvalidError(f"Token payload validation failed: {str(e)}")


def verify_access_token(token: str) -> TokenPayload:
    """
    Verify an access token.
    
    Args:
        token: JWT access token
        
    Returns:
        TokenPayload if valid
        
    Raises:
        TokenError: If token is invalid or not an access token
    """
    payload = decode_token(token)
    
    if payload.type != "access":
        raise TokenInvalidError("Not an access token")
    
    return payload


def verify_refresh_token(token: str) -> TokenPayload:
    """
    Verify a refresh token.
    
    Args:
        token: JWT refresh token
        
    Returns:
        TokenPayload if valid
        
    Raises:
        TokenError: If token is invalid or not a refresh token
    """
    payload = decode_token(token)
    
    if payload.type != "refresh":
        raise TokenInvalidError("Not a refresh token")
    
    return payload


def get_token_expiry(token: str) -> Optional[datetime]:
    """
    Get the expiration time of a token.
    
    Args:
        token: JWT token
        
    Returns:
        Datetime of expiration, or None if no expiration
    """
    try:
        payload = decode_token(token, verify_exp=False)
        if payload.exp:
            return datetime.fromtimestamp(payload.exp)
        return None
    except TokenError:
        return None


def is_token_expired(token: str) -> bool:
    """
    Check if a token is expired.
    
    Args:
        token: JWT token
        
    Returns:
        True if expired, False otherwise
    """
    try:
        decode_token(token)
        return False
    except TokenExpiredError:
        return True
    except TokenError:
        return True  # Invalid tokens are considered "expired" for security


def extract_token_from_header(authorization: str) -> str:
    """
    Extract JWT token from Authorization header.
    
    Expected format: "Bearer <token>"
    
    Args:
        authorization: Authorization header value
        
    Returns:
        JWT token string
        
    Raises:
        TokenInvalidError: If header format is invalid
    """
    parts = authorization.split()
    
    if len(parts) != 2:
        raise TokenInvalidError("Invalid authorization header format")
    
    scheme, token = parts
    
    if scheme.lower() != "bearer":
        raise TokenInvalidError("Invalid authentication scheme")
    
    return token


def get_token_claims(token: str) -> dict[str, Any]:
    """
    Get all claims from a token without full validation.
    
    Useful for debugging or getting claims from expired tokens.
    
    Args:
        token: JWT token
        
    Returns:
        Dictionary of all token claims
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"verify_exp": False}
        )
        return payload
    except JWTError:
        return {}


def verify_token(token: str, secret_key: str = None, expected_type: str = "access") -> TokenPayload:
    """
    Verify a JWT token.
    
    This is a convenience function that wraps decode_token for API usage.
    
    Args:
        token: JWT token string
        secret_key: Secret key (uses settings if not provided)
        expected_type: Expected token type ('access' or 'refresh')
        
    Returns:
        TokenPayload if valid
        
    Raises:
        TokenExpiredError: If token has expired
        TokenInvalidError: If token is invalid or wrong type
    """
    payload = decode_token(token)
    
    if expected_type and payload.type != expected_type:
        raise TokenInvalidError(f"Expected {expected_type} token, got {payload.type}")
    
    return payload


class TokenService:
    """
    Service class for token operations.
    
    Provides a class-based interface for token management.
    """
    
    @staticmethod
    def create_access_token(user_id: str, **kwargs) -> str:
        """Create an access token."""
        return create_access_token(user_id, **kwargs)
    
    @staticmethod
    def create_refresh_token(user_id: str) -> str:
        """Create a refresh token."""
        return create_refresh_token(user_id)
    
    @staticmethod
    def create_token_pair(user_id: str, **kwargs) -> "Token":
        """Create an access/refresh token pair."""
        return create_token_pair(user_id, **kwargs)
    
    @staticmethod
    def verify_access_token(token: str) -> TokenPayload:
        """Verify an access token."""
        return verify_access_token(token)
    
    @staticmethod
    def verify_refresh_token(token: str) -> TokenPayload:
        """Verify a refresh token."""
        return verify_refresh_token(token)
    
    @staticmethod
    def verify(token: str, expected_type: str = "access") -> TokenPayload:
        """Verify a token of expected type."""
        return verify_token(token, expected_type=expected_type)
    
    @staticmethod
    def decode(token: str, verify_exp: bool = True) -> TokenPayload:
        """Decode a token."""
        return decode_token(token, verify_exp)
    
    @staticmethod
    def is_expired(token: str) -> bool:
        """Check if token is expired."""
        return is_token_expired(token)
