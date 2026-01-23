"""
Google OAuth Service

Handles Google OAuth authentication and user linking.
"""

from datetime import UTC, datetime
from typing import Any

import httpx
import structlog
from pydantic import BaseModel, EmailStr, Field

from forge.config import get_settings
from forge.models.user import AuthProvider, User, UserInDB

logger = structlog.get_logger(__name__)


class GoogleUserInfo(BaseModel):
    """User info from Google OAuth token."""

    sub: str = Field(description="Google user ID")
    email: EmailStr = Field(description="Email address")
    email_verified: bool = Field(default=False, description="Email verification status")
    name: str | None = Field(default=None, description="Full name")
    given_name: str | None = Field(default=None, description="First name")
    family_name: str | None = Field(default=None, description="Last name")
    picture: str | None = Field(default=None, description="Profile picture URL")
    locale: str | None = Field(default=None, description="Locale")


class GoogleOAuthError(Exception):
    """Google OAuth error."""
    pass


class GoogleOAuthService:
    """Service for Google OAuth operations."""

    GOOGLE_TOKEN_INFO_URL = "https://oauth2.googleapis.com/tokeninfo"
    GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

    def __init__(self):
        settings = get_settings()
        self.client_id = settings.google_client_id
        self.client_secret = settings.google_client_secret

        if not self.client_id:
            logger.warning("Google OAuth not configured - GOOGLE_CLIENT_ID not set")

    @property
    def is_configured(self) -> bool:
        """Check if Google OAuth is configured."""
        return self.client_id is not None

    async def verify_id_token(self, id_token: str) -> GoogleUserInfo:
        """
        Verify a Google ID token and return user info.

        Args:
            id_token: The ID token from Google Sign-In

        Returns:
            GoogleUserInfo with verified user data

        Raises:
            GoogleOAuthError: If token verification fails
        """
        if not self.is_configured:
            raise GoogleOAuthError("Google OAuth is not configured")

        async with httpx.AsyncClient() as client:
            # Verify the token with Google
            response = await client.get(
                self.GOOGLE_TOKEN_INFO_URL,
                params={"id_token": id_token},
                timeout=10.0,
            )

            if response.status_code != 200:
                logger.warning(
                    "Google token verification failed",
                    status_code=response.status_code,
                    response=response.text[:200],
                )
                raise GoogleOAuthError("Invalid or expired Google token")

            token_data = response.json()

            # Verify the token was issued for our app
            if token_data.get("aud") != self.client_id:
                logger.warning(
                    "Token audience mismatch",
                    expected=self.client_id,
                    actual=token_data.get("aud"),
                )
                raise GoogleOAuthError("Token was not issued for this application")

            # Check token expiration
            exp = token_data.get("exp")
            if exp and int(exp) < datetime.now(UTC).timestamp():
                raise GoogleOAuthError("Token has expired")

            return GoogleUserInfo(
                sub=token_data["sub"],
                email=token_data["email"],
                email_verified=token_data.get("email_verified", "false") == "true",
                name=token_data.get("name"),
                given_name=token_data.get("given_name"),
                family_name=token_data.get("family_name"),
                picture=token_data.get("picture"),
            )

    async def get_or_create_user(
        self,
        google_user: GoogleUserInfo,
        user_repo: Any,  # UserRepository
    ) -> tuple[UserInDB, bool]:
        """
        Get existing user or create new one from Google OAuth.

        Args:
            google_user: Verified Google user info
            user_repo: User repository instance

        Returns:
            Tuple of (user, is_new_user)
        """
        # First, check if user exists by Google ID
        existing_by_google = await user_repo.get_by_google_id(google_user.sub)
        if existing_by_google:
            logger.info("Found existing user by Google ID", user_id=existing_by_google.id)
            return existing_by_google, False

        # Check if user exists by email (might want to link accounts)
        existing_by_email = await user_repo.get_by_email(google_user.email)
        if existing_by_email:
            # User exists with this email but no Google link
            # We can auto-link if email is verified from Google
            if google_user.email_verified:
                logger.info(
                    "Linking Google account to existing user by email",
                    user_id=existing_by_email.id,
                    google_id=google_user.sub,
                )
                await user_repo.link_google_account(
                    user_id=existing_by_email.id,
                    google_id=google_user.sub,
                    google_email=google_user.email,
                )
                # Refresh user data
                updated_user = await user_repo.get_by_id(existing_by_email.id)
                return updated_user, False
            else:
                raise GoogleOAuthError(
                    "An account with this email already exists. "
                    "Please sign in with your password and link Google in settings."
                )

        # Create new user
        logger.info("Creating new user from Google OAuth", google_id=google_user.sub)

        # Generate unique username from email or name
        base_username = self._generate_username(google_user)
        username = await self._ensure_unique_username(base_username, user_repo)

        new_user = await user_repo.create_google_user(
            username=username,
            email=google_user.email,
            display_name=google_user.name,
            avatar_url=google_user.picture,
            google_id=google_user.sub,
            google_email=google_user.email,
            is_verified=google_user.email_verified,
        )

        return new_user, True

    def _generate_username(self, google_user: GoogleUserInfo) -> str:
        """Generate a username from Google user info."""
        # Try email prefix first
        email_prefix = google_user.email.split("@")[0]
        # Clean it up - only alphanumeric, underscore, hyphen
        import re
        username = re.sub(r"[^a-zA-Z0-9_-]", "", email_prefix)

        # Ensure minimum length
        if len(username) < 3:
            if google_user.given_name:
                username = re.sub(r"[^a-zA-Z0-9_-]", "", google_user.given_name.lower())
            if len(username) < 3:
                username = "user"

        return username[:50]  # Max 50 chars

    async def _ensure_unique_username(self, base: str, user_repo: Any) -> str:
        """Ensure username is unique by appending numbers if needed."""
        username = base
        counter = 1

        while await user_repo.username_exists(username):
            username = f"{base}{counter}"
            counter += 1
            if counter > 1000:  # Prevent infinite loop
                import secrets
                username = f"{base}_{secrets.token_hex(4)}"
                break

        return username


# Singleton instance
_google_oauth_service: GoogleOAuthService | None = None


def get_google_oauth_service() -> GoogleOAuthService:
    """Get or create Google OAuth service instance."""
    global _google_oauth_service
    if _google_oauth_service is None:
        _google_oauth_service = GoogleOAuthService()
    return _google_oauth_service
