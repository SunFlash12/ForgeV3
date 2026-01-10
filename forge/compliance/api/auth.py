"""
Forge Compliance Framework - Authentication

JWT-based authentication for the compliance API.
Standalone authentication that doesn't depend on the main Forge API.
"""

from __future__ import annotations

import os
from datetime import datetime
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
import jwt


# Security scheme - auto_error=False to allow custom error handling
security = HTTPBearer(auto_error=False)


class TokenPayload(BaseModel):
    """JWT token payload."""
    sub: str  # User ID
    exp: datetime
    iat: datetime
    jti: str | None = None
    roles: list[str] = []
    permissions: list[str] = []


class ComplianceUser(BaseModel):
    """Authenticated user context for compliance operations."""
    id: str
    roles: list[str] = []
    permissions: list[str] = []
    is_admin: bool = False
    is_compliance_officer: bool = False


@lru_cache
def get_jwt_secret() -> str:
    """Get JWT secret from environment."""
    secret = os.getenv("COMPLIANCE_JWT_SECRET") or os.getenv("JWT_SECRET_KEY")
    if not secret:
        raise ValueError(
            "JWT secret not configured. Set COMPLIANCE_JWT_SECRET or JWT_SECRET_KEY environment variable."
        )
    return secret


def verify_token(token: str) -> TokenPayload | None:
    """Verify and decode a JWT token."""
    try:
        secret = get_jwt_secret()
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            options={"require": ["exp", "sub", "iat"]},
        )
        return TokenPayload(**payload)
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
    except Exception:
        return None


async def get_token_payload(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> TokenPayload | None:
    """
    Extract and verify token payload from cookie or Authorization header.
    """
    token = None

    # Priority 1: Check httpOnly cookie
    access_token_cookie = request.cookies.get("access_token")
    if access_token_cookie:
        token = access_token_cookie

    # Priority 2: Fall back to Authorization header
    if not token and credentials:
        token = credentials.credentials

    if not token:
        return None

    return verify_token(token)


async def get_current_user_optional(
    token: Annotated[TokenPayload | None, Depends(get_token_payload)],
) -> ComplianceUser | None:
    """Get current user if authenticated, None otherwise."""
    if not token:
        return None

    return ComplianceUser(
        id=token.sub,
        roles=token.roles,
        permissions=token.permissions,
        is_admin="admin" in token.roles,
        is_compliance_officer="compliance_officer" in token.roles or "admin" in token.roles,
    )


async def get_current_user(
    user: Annotated[ComplianceUser | None, Depends(get_current_user_optional)],
) -> ComplianceUser:
    """Require authenticated user."""
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def require_compliance_officer(
    user: Annotated[ComplianceUser, Depends(get_current_user)],
) -> ComplianceUser:
    """Require user to be a compliance officer or admin."""
    if not user.is_compliance_officer:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Compliance officer role required",
        )
    return user


async def require_admin(
    user: Annotated[ComplianceUser, Depends(get_current_user)],
) -> ComplianceUser:
    """Require user to be an admin."""
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return user


# Type aliases for use in routes
OptionalUserDep = Annotated[ComplianceUser | None, Depends(get_current_user_optional)]
CurrentUserDep = Annotated[ComplianceUser, Depends(get_current_user)]
ComplianceOfficerDep = Annotated[ComplianceUser, Depends(require_compliance_officer)]
AdminUserDep = Annotated[ComplianceUser, Depends(require_admin)]


def require_permission(permission_name: str, resource_type: str | None = None):
    """
    Dependency factory to require a specific permission.

    Uses the AccessControlService for fine-grained access control.
    """
    from forge.compliance.security.access_control import (
        get_access_control_service,
        Permission,
        ResourceType,
    )

    async def dependency(user: CurrentUserDep) -> ComplianceUser:
        access_control = get_access_control_service()

        try:
            perm = Permission(permission_name)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Unknown permission: {permission_name}",
            )

        res_type = None
        if resource_type:
            try:
                res_type = ResourceType(resource_type)
            except ValueError:
                pass

        decision = access_control.check_access(
            user_id=user.id,
            permission=perm,
            resource_type=res_type or ResourceType.SYSTEM_CONFIG,
        )

        if not decision.allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=decision.reason,
            )

        return user

    return dependency


__all__ = [
    "TokenPayload",
    "ComplianceUser",
    "get_current_user_optional",
    "get_current_user",
    "require_compliance_officer",
    "require_admin",
    "require_permission",
    "OptionalUserDep",
    "CurrentUserDep",
    "ComplianceOfficerDep",
    "AdminUserDep",
]
