# Forge V3 - Phase 6: API Layer

**Purpose:** Implement REST API endpoints using FastAPI with proper middleware and error handling.

**Estimated Effort:** 3-4 days
**Dependencies:** Phase 0-5
**Outputs:** Complete REST API with authentication, rate limiting, and documentation

---

## 1. Overview

The API layer exposes all Forge functionality via REST endpoints. Built with FastAPI for async support, automatic OpenAPI docs, and Pydantic validation.

---

## 2. API Dependencies

```python
# forge/api/dependencies.py
"""
FastAPI dependencies for injection into route handlers.
"""
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

from forge.config import get_settings, Settings
from forge.dependencies import get_neo4j, get_redis
from forge.models.user import User
from forge.core.users.repository import UserRepository
from forge.security.authorization import AuthorizationService, Permission
from forge.exceptions import AuthenticationError, AuthorizationError

security = HTTPBearer()


async def get_settings_dep() -> Settings:
    """Get application settings."""
    return get_settings()


async def get_user_repository() -> UserRepository:
    """Get user repository."""
    return UserRepository(get_neo4j())


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> User:
    """
    Extract and validate current user from JWT token.
    
    Used as dependency in protected routes.
    """
    token = credentials.credentials
    
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
        )
        
        if payload.get("type") != "access":
            raise AuthenticationError("Invalid token type")
        
        user_id = UUID(payload["sub"])
        user = await user_repo.get_by_id(user_id)
        
        if not user:
            raise AuthenticationError("User not found")
        
        if not user.is_active:
            raise AuthenticationError("User account is disabled")
        
        return user
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
        )


async def get_optional_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(HTTPBearer(auto_error=False))],
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> User | None:
    """Get current user if authenticated, None otherwise."""
    if not credentials:
        return None
    
    try:
        return await get_current_user(credentials, user_repo, settings)
    except HTTPException:
        return None


def require_permission(permission: Permission):
    """
    Dependency factory for permission checking.
    
    Usage:
        @router.get("/admin", dependencies=[Depends(require_permission(Permission.ADMIN_USERS))])
    """
    async def checker(
        user: Annotated[User, Depends(get_current_user)],
        auth_service: Annotated[AuthorizationService, Depends(lambda: AuthorizationService())],
    ):
        if not auth_service.check_permission(user, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permission: {permission.value}",
            )
        return user
    
    return checker


# Type aliases for cleaner route signatures
CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_optional_user)]
```

---

## 3. Auth Routes

```python
# forge/api/routes/auth.py
"""
Authentication endpoints.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, EmailStr

from forge.api.dependencies import get_user_repository, get_settings_dep, CurrentUser
from forge.core.users.repository import UserRepository
from forge.security.auth import AuthService
from forge.dependencies import get_redis
from forge.models.user import UserCreate, User
from forge.config import Settings
from forge.exceptions import AuthenticationError, ValidationError

router = APIRouter(prefix="/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: str | None = None


@router.post("/register", response_model=dict, status_code=status.HTTP_201_CREATED)
async def register(
    data: RegisterRequest,
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
):
    """Register a new user account."""
    auth_service = AuthService(user_repo, get_redis())
    
    try:
        user = await auth_service.register(
            UserCreate(
                email=data.email,
                password=data.password,
                display_name=data.display_name,
            )
        )
        
        return {
            "message": "Registration successful",
            "user_id": str(user.id),
        }
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/login", response_model=TokenResponse)
async def login(
    data: LoginRequest,
    request: Request,
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
):
    """Authenticate and receive access tokens."""
    auth_service = AuthService(user_repo, get_redis())
    
    # Get client IP
    ip_address = request.client.host if request.client else "unknown"
    
    try:
        user, access_token, refresh_token = await auth_service.authenticate(
            email=data.email,
            password=data.password,
            ip_address=ip_address,
        )
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.jwt_access_token_expire_minutes * 60,
        )
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_tokens(
    data: RefreshRequest,
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
):
    """Refresh access token using refresh token."""
    auth_service = AuthService(user_repo, get_redis())
    
    try:
        access_token, refresh_token = await auth_service.refresh_tokens(data.refresh_token)
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.jwt_access_token_expire_minutes * 60,
        )
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    current_user: CurrentUser,
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
):
    """Logout and revoke refresh token."""
    auth_service = AuthService(user_repo, get_redis())
    await auth_service.logout(current_user.id)


@router.get("/me", response_model=dict)
async def get_current_user_info(current_user: CurrentUser):
    """Get current user information."""
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "display_name": current_user.display_name,
        "trust_level": current_user.trust_level.value,
        "roles": current_user.roles,
        "created_at": current_user.created_at.isoformat(),
    }
```

---

## 4. Capsule Routes

```python
# forge/api/routes/capsules.py
"""
Capsule CRUD and search endpoints.
"""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel

from forge.api.dependencies import CurrentUser, get_user_repository
from forge.dependencies import get_neo4j
from forge.core.capsules.service import CapsuleService
from forge.core.capsules.repository import CapsuleRepository
from forge.infrastructure.embedding.service import create_embedding_service
from forge.models.capsule import (
    Capsule,
    CapsuleCreate,
    CapsuleUpdate,
    LineageResult,
)
from forge.models.search import SearchQuery, SearchResult
from forge.models.base import CapsuleType, TrustLevel, PaginationMeta, ApiResponse
from forge.exceptions import NotFoundError, AuthorizationError

router = APIRouter(prefix="/capsules", tags=["Capsules"])


def get_capsule_service() -> CapsuleService:
    """Get capsule service instance."""
    repo = CapsuleRepository(get_neo4j())
    embedding = create_embedding_service()
    return CapsuleService(repo, embedding)


CapsuleServiceDep = Annotated[CapsuleService, Depends(get_capsule_service)]


# Response models
class CapsuleResponse(BaseModel):
    data: Capsule


class CapsuleListResponse(BaseModel):
    data: list[Capsule]
    meta: PaginationMeta


class SearchResponse(BaseModel):
    data: list[SearchResult]
    query: str
    total: int


class LineageResponse(BaseModel):
    data: LineageResult


@router.post("", response_model=CapsuleResponse, status_code=status.HTTP_201_CREATED)
async def create_capsule(
    data: CapsuleCreate,
    current_user: CurrentUser,
    service: CapsuleServiceDep,
):
    """Create a new knowledge capsule."""
    try:
        capsule = await service.create(data, current_user)
        return CapsuleResponse(data=capsule)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except AuthorizationError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.get("", response_model=CapsuleListResponse)
async def list_capsules(
    current_user: CurrentUser,
    service: CapsuleServiceDep,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    type: CapsuleType | None = None,
    trust_level: TrustLevel | None = None,
    owner_id: UUID | None = None,
    parent_id: UUID | None = None,
):
    """List capsules with optional filters."""
    capsules, total = await service.list(
        user=current_user,
        page=page,
        per_page=per_page,
        type_filter=type,
        trust_level_filter=trust_level,
        owner_id=owner_id,
        parent_id=parent_id,
    )
    
    return CapsuleListResponse(
        data=capsules,
        meta=PaginationMeta.create(total, page, per_page),
    )


@router.get("/{capsule_id}", response_model=CapsuleResponse)
async def get_capsule(
    capsule_id: UUID,
    current_user: CurrentUser,
    service: CapsuleServiceDep,
):
    """Get a capsule by ID."""
    try:
        capsule = await service.get(capsule_id, current_user)
        return CapsuleResponse(data=capsule)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except AuthorizationError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.patch("/{capsule_id}", response_model=CapsuleResponse)
async def update_capsule(
    capsule_id: UUID,
    data: CapsuleUpdate,
    current_user: CurrentUser,
    service: CapsuleServiceDep,
):
    """Update a capsule."""
    try:
        capsule = await service.update(capsule_id, data, current_user)
        return CapsuleResponse(data=capsule)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except AuthorizationError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.delete("/{capsule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_capsule(
    capsule_id: UUID,
    current_user: CurrentUser,
    service: CapsuleServiceDep,
    cascade: bool = False,
):
    """Delete a capsule (soft delete)."""
    try:
        await service.delete(capsule_id, current_user, cascade)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except AuthorizationError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/search", response_model=SearchResponse)
async def search_capsules(
    query: SearchQuery,
    current_user: CurrentUser,
    service: CapsuleServiceDep,
):
    """Semantic search for capsules."""
    results = await service.search(
        query=query.query,
        user=current_user,
        limit=query.limit,
        min_score=query.min_score,
        type_filter=query.type,
    )
    
    return SearchResponse(
        data=[SearchResult(capsule=c, score=s) for c, s in results],
        query=query.query,
        total=len(results),
    )


@router.get("/{capsule_id}/lineage", response_model=LineageResponse)
async def get_capsule_lineage(
    capsule_id: UUID,
    current_user: CurrentUser,
    service: CapsuleServiceDep,
    max_depth: int = Query(default=10, ge=1, le=50),
):
    """Get the ancestry chain (Isnad) for a capsule."""
    try:
        lineage = await service.get_lineage(capsule_id, current_user, max_depth)
        return LineageResponse(data=lineage)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except AuthorizationError as e:
        raise HTTPException(status_code=403, detail=str(e))
```

---

## 5. Governance Routes

```python
# forge/api/routes/governance.py
"""
Governance endpoints for proposals and voting.
"""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from forge.api.dependencies import CurrentUser
from forge.dependencies import get_neo4j
from forge.core.governance.service import GovernanceService
from forge.core.governance.repository import GovernanceRepository
from forge.core.users.repository import UserRepository
from forge.models.governance import (
    Proposal,
    ProposalCreate,
    Vote,
    VoteCreate,
    ProposalStatus,
)
from forge.models.base import PaginationMeta
from forge.exceptions import NotFoundError, AuthorizationError, ValidationError

router = APIRouter(prefix="/governance", tags=["Governance"])


def get_governance_service() -> GovernanceService:
    """Get governance service."""
    neo4j = get_neo4j()
    return GovernanceService(
        repository=GovernanceRepository(neo4j),
        user_repository=UserRepository(neo4j),
    )


GovernanceServiceDep = Annotated[GovernanceService, Depends(get_governance_service)]


class ProposalResponse(BaseModel):
    data: Proposal


class ProposalListResponse(BaseModel):
    data: list[Proposal]
    meta: PaginationMeta


class VoteResponse(BaseModel):
    data: Vote


@router.post("/proposals", response_model=ProposalResponse, status_code=201)
async def create_proposal(
    data: ProposalCreate,
    current_user: CurrentUser,
    service: GovernanceServiceDep,
):
    """Create a new governance proposal."""
    try:
        proposal = await service.create_proposal(data, current_user)
        return ProposalResponse(data=proposal)
    except AuthorizationError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.get("/proposals", response_model=ProposalListResponse)
async def list_proposals(
    current_user: CurrentUser,
    service: GovernanceServiceDep,
    status: ProposalStatus | None = None,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
):
    """List governance proposals."""
    proposals, total = await service.list_proposals(status, page, per_page)
    
    return ProposalListResponse(
        data=proposals,
        meta=PaginationMeta.create(total, page, per_page),
    )


@router.get("/proposals/{proposal_id}", response_model=ProposalResponse)
async def get_proposal(
    proposal_id: UUID,
    current_user: CurrentUser,
    service: GovernanceServiceDep,
):
    """Get a proposal by ID."""
    proposal = await service.get_proposal(proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return ProposalResponse(data=proposal)


@router.post("/proposals/{proposal_id}/activate", response_model=ProposalResponse)
async def activate_proposal(
    proposal_id: UUID,
    current_user: CurrentUser,
    service: GovernanceServiceDep,
):
    """Activate a draft proposal to open voting."""
    try:
        proposal = await service.activate_proposal(proposal_id, current_user)
        return ProposalResponse(data=proposal)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (AuthorizationError, ValidationError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/proposals/{proposal_id}/vote", response_model=VoteResponse)
async def cast_vote(
    proposal_id: UUID,
    data: VoteCreate,
    current_user: CurrentUser,
    service: GovernanceServiceDep,
):
    """Cast or update a vote on a proposal."""
    try:
        vote = await service.cast_vote(proposal_id, data, current_user)
        return VoteResponse(data=vote)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (AuthorizationError, ValidationError) as e:
        raise HTTPException(status_code=400, detail=str(e))
```

---

## 6. Rate Limiting Middleware

```python
# forge/api/middleware/rate_limit.py
"""
Rate limiting middleware using Redis.
"""
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware

from forge.dependencies import get_redis
from forge.config import get_settings
from forge.models.base import TrustLevel


# Rate limits by trust level (requests per minute)
RATE_LIMITS = {
    TrustLevel.CORE: 10000,
    TrustLevel.TRUSTED: 2000,
    TrustLevel.STANDARD: 1000,
    TrustLevel.SANDBOX: 100,
    TrustLevel.QUARANTINE: 10,
}

DEFAULT_RATE_LIMIT = 100  # For unauthenticated requests


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Token bucket rate limiting.
    
    Limits vary by user trust level.
    """
    
    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks
        if request.url.path in ("/health", "/docs", "/openapi.json"):
            return await call_next(request)
        
        redis = get_redis()
        
        # Determine rate limit key and limit
        user = getattr(request.state, "user", None)
        
        if user:
            key = f"rate_limit:user:{user.id}"
            limit = RATE_LIMITS.get(user.trust_level, DEFAULT_RATE_LIMIT)
        else:
            # Use IP for unauthenticated requests
            ip = request.client.host if request.client else "unknown"
            key = f"rate_limit:ip:{ip}"
            limit = DEFAULT_RATE_LIMIT
        
        # Check current count
        current = await redis.increment(key, ttl=60)
        
        # Add rate limit headers
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, limit - current))
        response.headers["X-RateLimit-Reset"] = "60"
        
        if current > limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Limit: {limit}/minute",
                headers={
                    "Retry-After": "60",
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                },
            )
        
        return response
```

---

## 7. Request Logging Middleware

```python
# forge/api/middleware/logging.py
"""
Request/response logging middleware.
"""
import time
from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from forge.logging import get_logger

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log all requests with timing and correlation ID."""
    
    async def dispatch(self, request: Request, call_next):
        # Generate correlation ID
        correlation_id = str(uuid4())
        request.state.correlation_id = correlation_id
        
        # Log request
        start_time = time.perf_counter()
        
        logger.info(
            "request_started",
            correlation_id=correlation_id,
            method=request.method,
            path=request.url.path,
            client_ip=request.client.host if request.client else None,
        )
        
        try:
            response = await call_next(request)
            
            # Calculate duration
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            logger.info(
                "request_completed",
                correlation_id=correlation_id,
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=round(duration_ms, 2),
            )
            
            # Add correlation ID to response
            response.headers["X-Correlation-ID"] = correlation_id
            
            return response
            
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            logger.error(
                "request_failed",
                correlation_id=correlation_id,
                method=request.method,
                path=request.url.path,
                error=str(e),
                duration_ms=round(duration_ms, 2),
            )
            raise
```

---

## 8. Register Routes in Main App

```python
# forge/main.py (updated)
"""
FastAPI application with all routes registered.
"""
from forge.main import create_app as base_create_app
from forge.api.routes import auth, capsules, governance, overlays, system
from forge.api.middleware.rate_limit import RateLimitMiddleware
from forge.api.middleware.logging import RequestLoggingMiddleware


def create_app():
    """Create app with all routes and middleware."""
    app = base_create_app()
    
    # Add middleware (order matters - first added = outermost)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(RateLimitMiddleware)
    
    # Register route modules
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(capsules.router, prefix="/api/v1")
    app.include_router(governance.router, prefix="/api/v1")
    # app.include_router(overlays.router, prefix="/api/v1")
    # app.include_router(system.router, prefix="/api/v1")
    
    return app


app = create_app()
```

---

## 9. Next Steps

After completing Phase 6, proceed to **Phase 7: Interfaces** to implement:

- Command Line Interface (Typer)
- Web Dashboard (React)
- Mobile App structure (React Native)
