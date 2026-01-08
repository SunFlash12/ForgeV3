"""
Forge Cascade Configuration Management

Centralized configuration using Pydantic Settings for type-safe environment
variable loading with validation.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ═══════════════════════════════════════════════════════════════
    # APPLICATION
    # ═══════════════════════════════════════════════════════════════
    app_name: str = Field(default="forge-cascade", description="Application name")
    app_env: Literal["development", "staging", "production"] = Field(
        default="development", description="Environment"
    )
    debug: bool = Field(default=False, description="Debug mode")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", description="Logging level"
    )

    # API Server
    api_host: str = Field(default="0.0.0.0", description="API host")
    api_port: int = Field(default=8000, ge=1, le=65535, description="API port")
    api_workers: int = Field(default=4, ge=1, description="Number of workers")

    # CORS
    cors_origins: str = Field(
        default="http://localhost:3000,http://localhost:8000",
        description="Comma-separated CORS origins",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins string into list."""
        origins = [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
        # Security: Never allow wildcard with credentials in production
        if self.app_env == "production" and "*" in origins:
            raise ValueError("Wildcard CORS origin not allowed in production")
        return origins

    # Expose as CORS_ORIGINS for backwards compatibility
    @property
    def CORS_ORIGINS(self) -> list[str]:
        """CORS origins as list (alias for cors_origins_list)."""
        return self.cors_origins_list

    # ═══════════════════════════════════════════════════════════════
    # NEO4J DATABASE
    # ═══════════════════════════════════════════════════════════════
    neo4j_uri: str = Field(description="Neo4j connection URI")
    neo4j_user: str = Field(default="neo4j", description="Neo4j username")
    neo4j_password: str = Field(description="Neo4j password")
    neo4j_database: str = Field(default="neo4j", description="Neo4j database name")

    # Connection Pool
    neo4j_max_connection_lifetime: int = Field(
        default=3600, description="Max connection lifetime in seconds"
    )
    neo4j_max_connection_pool_size: int = Field(
        default=50, ge=1, description="Max connection pool size"
    )
    neo4j_connection_timeout: int = Field(
        default=30, ge=1, description="Connection timeout in seconds"
    )

    # ═══════════════════════════════════════════════════════════════
    # REDIS CACHE (Optional)
    # ═══════════════════════════════════════════════════════════════
    redis_url: str | None = Field(default=None, description="Redis URL")
    redis_password: str | None = Field(default=None, description="Redis password")
    cache_ttl_seconds: int = Field(default=3600, ge=0, description="Cache TTL")

    # ═══════════════════════════════════════════════════════════════
    # SECURITY
    # ═══════════════════════════════════════════════════════════════
    jwt_secret_key: str = Field(description="JWT secret key")
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
    jwt_access_token_expire_minutes: int = Field(
        default=60, ge=1, description="Access token expiry"
    )
    jwt_refresh_token_expire_days: int = Field(
        default=7, ge=1, description="Refresh token expiry"
    )
    password_bcrypt_rounds: int = Field(
        default=12, ge=4, le=31, description="Bcrypt rounds"
    )

    @field_validator("jwt_secret_key")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("JWT secret key must be at least 32 characters")
        # Check for sufficient entropy (not just repeated characters)
        unique_chars = len(set(v))
        if unique_chars < 10:
            raise ValueError("JWT secret key must have at least 10 unique characters for sufficient entropy")
        # Check it's not a simple pattern
        if v == v[0] * len(v):
            raise ValueError("JWT secret key cannot be a repeated character")
        return v

    # ═══════════════════════════════════════════════════════════════
    # AI/ML CONFIGURATION
    # ═══════════════════════════════════════════════════════════════
    llm_provider: Literal["anthropic", "openai", "ollama", "mock"] = Field(
        default="mock", description="LLM provider"
    )
    llm_api_key: str | None = Field(default=None, description="LLM API key")
    llm_model: str = Field(
        default="claude-sonnet-4-20250514", description="LLM model name"
    )
    # Cost optimization: Reduced from 4096 - Ghost Council responses typically 500-800 tokens
    llm_max_tokens: int = Field(default=2000, ge=1, description="Max LLM output tokens")
    # Cost optimization: Lower temperature for more consistent, cacheable responses
    llm_temperature: float = Field(default=0.4, ge=0.0, le=2.0, description="LLM temperature")

    # Embeddings
    embedding_provider: Literal["openai", "sentence_transformers", "mock"] = Field(
        default="mock", description="Embedding provider"
    )
    embedding_api_key: str | None = Field(default=None, description="Embedding API key (for OpenAI)")
    embedding_model: str = Field(
        default="text-embedding-3-small", description="Embedding model"
    )
    embedding_dimensions: int = Field(
        default=1536, ge=1, description="Embedding dimensions"
    )
    embedding_cache_enabled: bool = Field(default=True, description="Cache embeddings")
    embedding_batch_size: int = Field(default=100, ge=1, description="Batch size for embedding")
    # Cost optimization: Increased from 10000 for better cache hit rates
    embedding_cache_size: int = Field(default=50000, ge=1000, description="Max embedding cache entries")

    # ═══════════════════════════════════════════════════════════════
    # GHOST COUNCIL
    # ═══════════════════════════════════════════════════════════════
    # Cost optimization: Profile controls how many council members deliberate
    # - "quick": 1 member (Ethics) - fastest, lowest cost
    # - "standard": 3 members (Ethics, Security, Governance) - balanced
    # - "comprehensive": 5 members (all) - full deliberation
    ghost_council_profile: Literal["quick", "standard", "comprehensive"] = Field(
        default="comprehensive", description="Ghost Council deliberation profile"
    )
    # Cache Ghost Council opinions to avoid re-deliberation on identical proposals
    ghost_council_cache_enabled: bool = Field(default=True, description="Cache council opinions")
    ghost_council_cache_ttl_days: int = Field(default=30, ge=1, description="Opinion cache TTL in days")

    # ═══════════════════════════════════════════════════════════════
    # IMMUNE SYSTEM
    # ═══════════════════════════════════════════════════════════════
    # Circuit Breaker
    circuit_breaker_failure_threshold: int = Field(
        default=3, ge=1, description="Failures before opening"
    )
    circuit_breaker_success_threshold: int = Field(
        default=2, ge=1, description="Successes to close"
    )
    circuit_breaker_timeout_seconds: int = Field(
        default=30, ge=1, description="Timeout in open state"
    )

    # Canary Deployments
    canary_initial_traffic_percent: float = Field(
        default=0.05, ge=0.0, le=1.0, description="Initial canary traffic"
    )
    canary_min_requests: int = Field(
        default=100, ge=1, description="Min requests before decision"
    )
    canary_max_error_rate: float = Field(
        default=0.01, ge=0.0, le=1.0, description="Max error rate"
    )
    canary_max_latency_ratio: float = Field(
        default=2.0, ge=1.0, description="Max latency ratio"
    )

    # Health Checks
    health_check_interval_seconds: int = Field(
        default=30, ge=1, description="Health check interval"
    )
    auto_quarantine_threshold: int = Field(
        default=3, ge=1, description="Failures before quarantine"
    )

    # ═══════════════════════════════════════════════════════════════
    # PIPELINE
    # ═══════════════════════════════════════════════════════════════
    pipeline_timeout_seconds: int = Field(
        default=30, ge=1, description="Pipeline timeout"
    )
    pipeline_max_concurrent: int = Field(
        default=10, ge=1, description="Max concurrent pipelines"
    )
    pipeline_cache_enabled: bool = Field(
        default=True, description="Enable pipeline caching"
    )

    # ═══════════════════════════════════════════════════════════════
    # MONITORING
    # ═══════════════════════════════════════════════════════════════
    prometheus_enabled: bool = Field(default=False, description="Enable Prometheus")
    prometheus_port: int = Field(default=9090, description="Prometheus port")

    jaeger_enabled: bool = Field(default=False, description="Enable Jaeger")
    jaeger_host: str = Field(default="localhost", description="Jaeger host")
    jaeger_port: int = Field(default=6831, description="Jaeger port")

    sentry_dsn: str | None = Field(default=None, description="Sentry DSN")

    # ═══════════════════════════════════════════════════════════════
    # SCHEDULER
    # ═══════════════════════════════════════════════════════════════
    scheduler_enabled: bool = Field(
        default=True, description="Enable background scheduler"
    )
    graph_snapshot_interval_minutes: int = Field(
        default=60, ge=5, description="Interval for automatic graph snapshots"
    )
    graph_snapshot_enabled: bool = Field(
        default=True, description="Enable automatic graph snapshots"
    )
    version_compaction_interval_hours: int = Field(
        default=24, ge=1, description="Interval for version compaction"
    )
    version_compaction_enabled: bool = Field(
        default=True, description="Enable automatic version compaction"
    )
    query_cache_cleanup_interval_minutes: int = Field(
        default=30, ge=5, description="Interval for query cache cleanup"
    )

    # ═══════════════════════════════════════════════════════════════
    # QUERY CACHING (Redis-backed NL→Cypher cache)
    # ═══════════════════════════════════════════════════════════════
    query_cache_enabled: bool = Field(
        default=True, description="Enable NL→Cypher query result caching"
    )
    query_cache_ttl_seconds: int = Field(
        default=3600, ge=60, description="TTL for cached query results"
    )
    query_cache_max_size: int = Field(
        default=10000, ge=100, description="Max cached query entries"
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Singleton settings instance
settings = get_settings()
