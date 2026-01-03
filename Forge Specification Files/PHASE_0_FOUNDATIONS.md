# Forge V3 - Phase 0: Foundations & Shared Components

**Purpose:** This document provides the architectural overview and shared components needed by all other phases. Read this first before implementing any phase.

**Estimated Effort:** 1-2 days
**Dependencies:** None (this is the foundation)

---

## 1. What is Forge?

Forge Cascade is an **Institutional Memory Engine** that solves the problem of ephemeral wisdom in AI systems. When AI models are upgraded or migrated, they lose accumulated knowledge. Forge creates a persistent layer that captures, preserves, and propagates knowledge across AI generations.

**Three Core Capabilities:**

1. **Persistent Knowledge Capsules** - Versioned containers storing institutional wisdom
2. **Isnad Lineage Tracking** - Unbroken chain of knowledge provenance (like scholarly citation chains)
3. **Self-Governing Intelligence** - Democratic governance with self-healing immune systems

---

## 2. Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| Database | Neo4j 5.x | Graph + Vector + Properties in single ACID store |
| Cache | Redis 7.x | Session storage, rate limiting, caching |
| Events | Kafka / KurrentDB | Event sourcing, audit trail |
| Runtime | Wasmtime | WebAssembly overlay execution |
| API | FastAPI + Pydantic v2 | Async REST API |
| Web UI | React 18 + Shadcn/UI | Dashboard interface |
| CLI | Typer + Rich | Command line interface |
| Mobile | React Native | iOS/Android monitoring app |

---

## 3. Project Structure

```
forge/
├── pyproject.toml              # Python project config
├── forge/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app factory
│   ├── config.py               # Settings management
│   ├── dependencies.py         # Dependency injection
│   │
│   ├── models/                 # Shared Pydantic models
│   │   ├── __init__.py
│   │   ├── base.py             # Base model classes
│   │   ├── capsule.py          # Capsule models
│   │   ├── user.py             # User models
│   │   ├── governance.py       # Governance models
│   │   ├── overlay.py          # Overlay models
│   │   └── events.py           # Event models
│   │
│   ├── core/                   # Core business logic
│   │   ├── __init__.py
│   │   ├── capsules/           # Capsule service (Phase 2)
│   │   ├── overlays/           # Overlay runtime (Phase 3)
│   │   ├── governance/         # Governance system (Phase 4)
│   │   └── compliance/         # Compliance framework (Phase 5)
│   │
│   ├── infrastructure/         # External integrations
│   │   ├── __init__.py
│   │   ├── neo4j/              # Neo4j client (Phase 1)
│   │   ├── redis/              # Redis client
│   │   ├── kafka/              # Kafka producer/consumer
│   │   └── embedding/          # Embedding service
│   │
│   ├── api/                    # API layer (Phase 6)
│   │   ├── __init__.py
│   │   ├── routes/
│   │   ├── middleware/
│   │   └── dependencies.py
│   │
│   └── security/               # Security (Phase 5)
│       ├── __init__.py
│       ├── auth.py
│       ├── encryption.py
│       └── authorization.py
│
├── tests/                      # Test suite
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
├── cli/                        # CLI application (Phase 7)
│   └── forge_cli/
│
└── deployment/                 # Deployment configs (Phase 8)
    ├── docker/
    ├── kubernetes/
    └── terraform/
```

---

## 4. Configuration System

```python
# forge/config.py
"""
Application configuration using Pydantic Settings.

Environment variables override defaults.
Secrets should come from environment or secret manager.
"""
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    
    # Application
    app_name: str = "Forge Cascade"
    app_version: str = "3.0.0"
    environment: str = Field(default="development", pattern="^(development|staging|production)$")
    debug: bool = False
    log_level: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4
    
    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: SecretStr
    neo4j_database: str = "neo4j"
    neo4j_max_connection_pool_size: int = 50
    
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_max_connections: int = 20
    
    # Kafka
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_consumer_group: str = "forge-api"
    
    # JWT Authentication
    jwt_secret: SecretStr
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7
    
    # Embedding Service
    embedding_provider: str = Field(default="openai", pattern="^(openai|local|azure)$")
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    openai_api_key: SecretStr | None = None
    
    # Security
    cors_origins: list[str] = ["http://localhost:3000"]
    rate_limit_requests_per_minute: int = 100
    
    # Feature Flags
    feature_governance_enabled: bool = True
    feature_overlays_enabled: bool = True
    feature_compliance_logging: bool = True
    
    @field_validator("neo4j_uri")
    @classmethod
    def validate_neo4j_uri(cls, v: str) -> str:
        if not v.startswith(("bolt://", "neo4j://", "bolt+s://", "neo4j+s://")):
            raise ValueError("neo4j_uri must start with bolt:// or neo4j://")
        return v


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
```

---

## 5. Shared Enums and Constants

```python
# forge/models/base.py
"""
Base models and shared enumerations used across all phases.
"""
from enum import Enum
from datetime import datetime, timezone
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, ConfigDict
from typing import Any


# =============================================================================
# ENUMERATIONS
# =============================================================================

class TrustLevel(str, Enum):
    """
    Trust level hierarchy for access control.
    
    Higher numeric values = more trust = more privileges.
    """
    CORE = "core"           # 100 - System critical, immune to quarantine
    TRUSTED = "trusted"     # 80 - Verified reliable, full privileges
    STANDARD = "standard"   # 60 - Default level, normal operations
    SANDBOX = "sandbox"     # 40 - Experimental, limited access
    QUARANTINE = "quarantine"  # 0 - Blocked, no execution
    
    @property
    def numeric_value(self) -> int:
        """Get numeric value for comparison."""
        values = {
            TrustLevel.CORE: 100,
            TrustLevel.TRUSTED: 80,
            TrustLevel.STANDARD: 60,
            TrustLevel.SANDBOX: 40,
            TrustLevel.QUARANTINE: 0,
        }
        return values[self]
    
    def can_access(self, required: "TrustLevel") -> bool:
        """Check if this trust level can access resources at required level."""
        return self.numeric_value >= required.numeric_value


class CapsuleType(str, Enum):
    """Classification of capsule content."""
    KNOWLEDGE = "knowledge"  # Facts, documentation, information
    CODE = "code"            # Source code, algorithms
    DECISION = "decision"    # Recorded decisions with rationale
    INSIGHT = "insight"      # Patterns, observations, lessons
    CONFIG = "config"        # System configuration
    POLICY = "policy"        # Organizational rules


class ProposalStatus(str, Enum):
    """Governance proposal lifecycle states."""
    DRAFT = "draft"          # Being written, not yet submitted
    ACTIVE = "active"        # Open for voting
    CLOSED = "closed"        # Voting ended, awaiting execution
    APPROVED = "approved"    # Passed, will be executed
    REJECTED = "rejected"    # Failed to pass
    EXECUTED = "executed"    # Successfully applied
    FAILED = "failed"        # Execution failed


class ProposalType(str, Enum):
    """Types of governance proposals."""
    CONFIGURATION = "configuration"
    POLICY = "policy"
    TRUST_ADJUSTMENT = "trust_adjustment"
    OVERLAY_REGISTRATION = "overlay_registration"
    OVERLAY_UPDATE = "overlay_update"
    EMERGENCY = "emergency"


class OverlayState(str, Enum):
    """Overlay lifecycle states."""
    PENDING = "pending"      # Awaiting approval
    ACTIVE = "active"        # Running normally
    SUSPENDED = "suspended"  # Temporarily disabled
    QUARANTINED = "quarantined"  # Isolated due to issues
    DEPRECATED = "deprecated"    # Being phased out


class VoteDecision(str, Enum):
    """Voting options."""
    FOR = "for"
    AGAINST = "against"
    ABSTAIN = "abstain"


# =============================================================================
# BASE MODELS
# =============================================================================

class ForgeBaseModel(BaseModel):
    """Base model with common configuration."""
    
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        use_enum_values=True,
        str_strip_whitespace=True,
    )


class TimestampMixin(BaseModel):
    """Mixin for created/updated timestamps."""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class IdentifiableMixin(BaseModel):
    """Mixin for entities with UUIDs."""
    id: UUID = Field(default_factory=uuid4)


# =============================================================================
# RESPONSE MODELS
# =============================================================================

class PaginationMeta(ForgeBaseModel):
    """Pagination metadata for list responses."""
    total: int
    page: int
    per_page: int
    pages: int
    
    @classmethod
    def create(cls, total: int, page: int, per_page: int) -> "PaginationMeta":
        return cls(
            total=total,
            page=page,
            per_page=per_page,
            pages=(total + per_page - 1) // per_page if per_page > 0 else 0,
        )


class ApiResponse(ForgeBaseModel):
    """Standard API response wrapper."""
    data: Any
    meta: dict | None = None
    links: dict | None = Field(default=None, alias="_links")


class ErrorDetail(ForgeBaseModel):
    """Field-level error detail."""
    field: str
    message: str
    code: str


class ErrorResponse(ForgeBaseModel):
    """Standard error response."""
    code: str
    message: str
    details: dict | None = None
    errors: list[ErrorDetail] | None = None
    documentation_url: str | None = None
```

---

## 6. Exception Hierarchy

```python
# forge/exceptions.py
"""
Application exception hierarchy.

All exceptions inherit from ForgeError and map to HTTP status codes.
"""
from typing import Any


class ForgeError(Exception):
    """Base exception for all Forge errors."""
    
    status_code: int = 500
    code: str = "internal_error"
    
    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.cause = cause
    
    def to_dict(self) -> dict:
        """Convert to API error response format."""
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }


class ValidationError(ForgeError):
    """Input validation failed."""
    status_code = 422
    code = "validation_error"
    
    def __init__(self, message: str, field: str | None = None, **kwargs):
        super().__init__(message, **kwargs)
        if field:
            self.details["field"] = field


class AuthenticationError(ForgeError):
    """Authentication failed."""
    status_code = 401
    code = "authentication_error"
    
    def __init__(self, message: str = "Authentication required", **kwargs):
        super().__init__(message, **kwargs)


class AuthorizationError(ForgeError):
    """Authorization failed."""
    status_code = 403
    code = "authorization_error"
    
    def __init__(self, message: str = "Permission denied", **kwargs):
        super().__init__(message, **kwargs)


class NotFoundError(ForgeError):
    """Resource not found."""
    status_code = 404
    code = "not_found"
    
    def __init__(self, resource: str, identifier: str, **kwargs):
        message = f"{resource} not found: {identifier}"
        super().__init__(message, **kwargs)
        self.details["resource"] = resource
        self.details["identifier"] = identifier


class ConflictError(ForgeError):
    """Resource conflict."""
    status_code = 409
    code = "conflict"


class RateLimitError(ForgeError):
    """Rate limit exceeded."""
    status_code = 429
    code = "rate_limit_exceeded"
    
    def __init__(self, retry_after: int, **kwargs):
        message = f"Rate limit exceeded. Retry after {retry_after} seconds."
        super().__init__(message, **kwargs)
        self.details["retry_after"] = retry_after


class ServiceUnavailableError(ForgeError):
    """External service unavailable."""
    status_code = 503
    code = "service_unavailable"
```

---

## 7. Logging Setup

```python
# forge/logging.py
"""
Structured logging configuration using structlog.
"""
import logging
import sys
import structlog
from forge.config import get_settings


def setup_logging() -> None:
    """Configure structured logging for the application."""
    settings = get_settings()
    
    # Configure structlog processors
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]
    
    if settings.environment == "development":
        # Pretty console output for development
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]
    else:
        # JSON output for production
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level),
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a logger instance."""
    return structlog.get_logger(name)
```

---

## 8. Dependency Injection

```python
# forge/dependencies.py
"""
Dependency injection setup for FastAPI.
"""
from typing import AsyncGenerator
from fastapi import Depends
from forge.config import Settings, get_settings
from forge.infrastructure.neo4j.client import Neo4jClient
from forge.infrastructure.redis.client import RedisClient


# Singleton instances (initialized on startup)
_neo4j_client: Neo4jClient | None = None
_redis_client: RedisClient | None = None


async def init_dependencies(settings: Settings) -> None:
    """Initialize all dependencies on application startup."""
    global _neo4j_client, _redis_client
    
    _neo4j_client = Neo4jClient(
        uri=settings.neo4j_uri,
        user=settings.neo4j_user,
        password=settings.neo4j_password.get_secret_value(),
        database=settings.neo4j_database,
    )
    await _neo4j_client.connect()
    
    _redis_client = RedisClient(url=settings.redis_url)
    await _redis_client.connect()


async def shutdown_dependencies() -> None:
    """Cleanup dependencies on application shutdown."""
    global _neo4j_client, _redis_client
    
    if _neo4j_client:
        await _neo4j_client.close()
    if _redis_client:
        await _redis_client.close()


def get_neo4j() -> Neo4jClient:
    """Get Neo4j client dependency."""
    if _neo4j_client is None:
        raise RuntimeError("Neo4j client not initialized")
    return _neo4j_client


def get_redis() -> RedisClient:
    """Get Redis client dependency."""
    if _redis_client is None:
        raise RuntimeError("Redis client not initialized")
    return _redis_client
```

---

## 9. Application Factory

```python
# forge/main.py
"""
FastAPI application factory.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from forge.config import get_settings
from forge.dependencies import init_dependencies, shutdown_dependencies
from forge.exceptions import ForgeError
from forge.logging import setup_logging, get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown."""
    settings = get_settings()
    
    # Startup
    setup_logging()
    logger.info("starting_application", version=settings.app_version)
    
    await init_dependencies(settings)
    logger.info("dependencies_initialized")
    
    yield
    
    # Shutdown
    logger.info("shutting_down_application")
    await shutdown_dependencies()


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    settings = get_settings()
    
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url="/redoc" if settings.environment != "production" else None,
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Exception handler for ForgeError
    @app.exception_handler(ForgeError)
    async def forge_error_handler(request: Request, exc: ForgeError):
        logger.warning(
            "api_error",
            error_code=exc.code,
            message=exc.message,
            path=request.url.path,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.to_dict(),
        )
    
    # Health check endpoint
    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "version": settings.app_version}
    
    # Import and register routers (added in Phase 6)
    # from forge.api.routes import capsules, governance, overlays, system
    # app.include_router(capsules.router, prefix="/api/v1")
    # app.include_router(governance.router, prefix="/api/v1")
    # app.include_router(overlays.router, prefix="/api/v1")
    # app.include_router(system.router, prefix="/api/v1")
    
    return app


# For running directly with uvicorn
app = create_app()
```

---

## 10. Environment Template

```bash
# .env.example - Copy to .env and fill in values

# Application
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG

# Server
HOST=0.0.0.0
PORT=8000

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password_here
NEO4J_DATABASE=neo4j

# Redis
REDIS_URL=redis://localhost:6379/0

# Kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:9092

# JWT
JWT_SECRET=your-super-secret-jwt-key-change-in-production

# Embedding
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
OPENAI_API_KEY=sk-your-key-here

# CORS
CORS_ORIGINS=["http://localhost:3000"]
```

---

## 11. Docker Compose for Development

```yaml
# docker-compose.yml
version: '3.8'

services:
  neo4j:
    image: neo4j:5.15-enterprise
    environment:
      NEO4J_AUTH: neo4j/development_password
      NEO4J_ACCEPT_LICENSE_AGREEMENT: "yes"
      NEO4J_PLUGINS: '["apoc"]'
      NEO4J_dbms_security_procedures_unrestricted: apoc.*
    ports:
      - "7474:7474"  # HTTP
      - "7687:7687"  # Bolt
    volumes:
      - neo4j_data:/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  kafka:
    image: confluentinc/cp-kafka:7.5.0
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9092
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
    ports:
      - "9092:9092"
    depends_on:
      - zookeeper

  zookeeper:
    image: confluentinc/cp-zookeeper:7.5.0
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181

volumes:
  neo4j_data:
  redis_data:
```

---

## 12. pyproject.toml

```toml
[project]
name = "forge"
version = "3.0.0"
description = "Forge Cascade - Institutional Memory Engine"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.109.0",
    "uvicorn[standard]>=0.27.0",
    "pydantic>=2.5.0",
    "pydantic-settings>=2.1.0",
    "neo4j>=5.15.0",
    "redis>=5.0.0",
    "aiokafka>=0.10.0",
    "httpx>=0.26.0",
    "structlog>=24.1.0",
    "argon2-cffi>=23.1.0",
    "PyJWT>=2.8.0",
    "wasmtime>=16.0.0",
    "openai>=1.10.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=4.1.0",
    "hypothesis>=6.92.0",
    "black>=24.1.0",
    "ruff>=0.1.14",
    "mypy>=1.8.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.black]
line-length = 100
target-version = ["py311"]

[tool.ruff]
line-length = 100
select = ["E", "F", "I", "N", "W", "UP"]

[tool.mypy]
python_version = "3.11"
strict = true
```

---

## Next Steps

After completing Phase 0 setup:

1. **Phase 1: Data Layer** - Implement Neo4j client and core repositories
2. **Phase 2: Knowledge Engine** - Build capsule service with embeddings and search
3. **Phase 3: Overlays** - WebAssembly runtime and overlay execution
4. **Phase 4: Governance** - Proposals, voting, immune system
5. **Phase 5: Security** - Authentication, authorization, encryption
6. **Phase 6: API** - REST endpoints and middleware
7. **Phase 7: Interfaces** - Web dashboard, CLI, mobile
8. **Phase 8: DevOps** - Deployment, testing, migration

Each phase builds on the foundations established here.
