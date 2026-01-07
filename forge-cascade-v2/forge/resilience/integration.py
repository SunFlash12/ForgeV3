"""
Resilience Integration
======================

Integrates resilience components with the Forge API layer.
Provides middleware, decorators, and helper functions.
"""

from __future__ import annotations

import time
from functools import wraps
from typing import Any, Callable, Optional, TypeVar
from datetime import datetime

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from forge.resilience.config import get_resilience_config
from forge.resilience.observability.tracing import get_tracer, OperationType
from forge.resilience.observability.metrics import get_metrics
from forge.resilience.caching.query_cache import get_query_cache, QueryCache
from forge.resilience.caching.cache_invalidation import get_cache_invalidator, CacheInvalidator
from forge.resilience.security.content_validator import get_content_validator, ValidationResult, ThreatLevel

logger = structlog.get_logger(__name__)

F = TypeVar('F', bound=Callable[..., Any])


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """
    Middleware for request tracing and metrics collection.

    Integrates OpenTelemetry tracing and Prometheus metrics
    with every HTTP request.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        tracer = get_tracer()
        metrics = get_metrics()

        # Extract path template for metrics (avoid high cardinality)
        path = request.url.path
        path_template = self._get_path_template(path)

        start_time = time.perf_counter()

        # Start trace span
        with tracer.span(
            f"HTTP {request.method} {path_template}",
            attributes={
                "http.method": request.method,
                "http.url": str(request.url),
                "http.route": path_template,
            }
        ) as span:
            try:
                response = await call_next(request)

                # Record success
                latency = time.perf_counter() - start_time
                metrics.request_latency(
                    latency=latency,
                    method=request.method,
                    endpoint=path_template,
                    status=response.status_code,
                )

                # Add response info to span
                if hasattr(span, 'set_attribute'):
                    span.set_attribute("http.status_code", response.status_code)

                return response

            except Exception as e:
                # Record error
                latency = time.perf_counter() - start_time
                metrics.request_latency(
                    latency=latency,
                    method=request.method,
                    endpoint=path_template,
                    status=500,
                )
                metrics.error("unhandled_exception", path_template)

                raise

    def _get_path_template(self, path: str) -> str:
        """Convert path to template for metrics (replace IDs with placeholders)."""
        import re

        # Replace UUIDs and common ID patterns
        path = re.sub(r'/cap_[a-f0-9]+', '/{capsule_id}', path)
        path = re.sub(r'/[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}', '/{id}', path)
        path = re.sub(r'/[a-f0-9]{24,}', '/{id}', path)

        return path


class ResilienceState:
    """
    Holds initialized resilience components.

    Attached to FastAPI app.state for access in routes.
    """

    def __init__(self):
        self.cache: Optional[QueryCache] = None
        self.invalidator: Optional[CacheInvalidator] = None
        self.validator = None
        self.tracer = None
        self.metrics = None
        self.initialized = False

    async def initialize(self) -> None:
        """Initialize all resilience components."""
        if self.initialized:
            return

        config = get_resilience_config()

        # Initialize caching
        if config.cache.enabled:
            self.cache = await get_query_cache()
            self.invalidator = await get_cache_invalidator()
            logger.info("resilience_cache_initialized")

        # Initialize content validator
        if config.content_validation.enabled:
            self.validator = get_content_validator()
            logger.info("resilience_validator_initialized")

        # Initialize observability
        if config.observability.enabled:
            self.tracer = get_tracer()
            self.metrics = get_metrics()
            logger.info("resilience_observability_initialized")

        self.initialized = True
        logger.info("resilience_fully_initialized")

    async def close(self) -> None:
        """Clean up resilience components."""
        if self.cache:
            await self.cache.close()
        if self.invalidator:
            await self.invalidator.close()

        self.initialized = False


# Global resilience state
_resilience_state: Optional[ResilienceState] = None


async def get_resilience_state() -> ResilienceState:
    """Get or create the global resilience state."""
    global _resilience_state
    if _resilience_state is None:
        _resilience_state = ResilienceState()
        await _resilience_state.initialize()
    return _resilience_state


async def initialize_resilience(app) -> None:
    """Initialize resilience components for a FastAPI app."""
    state = await get_resilience_state()
    app.state.resilience = state
    logger.info("resilience_attached_to_app")


async def shutdown_resilience(app) -> None:
    """Shutdown resilience components."""
    if hasattr(app.state, 'resilience'):
        await app.state.resilience.close()
    logger.info("resilience_shutdown")


# =============================================================================
# Caching Helpers
# =============================================================================

async def get_cached_capsule(capsule_id: str) -> Optional[dict]:
    """Get a capsule from cache."""
    state = await get_resilience_state()
    if not state.cache:
        return None

    config = get_resilience_config()
    key = config.cache.capsule_key_pattern.format(capsule_id=capsule_id)
    return await state.cache.get(key)


async def cache_capsule(capsule_id: str, capsule_data: dict, ttl: int = 300) -> bool:
    """Cache a capsule."""
    state = await get_resilience_state()
    if not state.cache:
        return False

    config = get_resilience_config()
    key = config.cache.capsule_key_pattern.format(capsule_id=capsule_id)
    return await state.cache.set(
        key,
        capsule_data,
        ttl=ttl,
        query_type="capsule",
        related_capsule_ids=[capsule_id]
    )


async def invalidate_capsule_cache(capsule_id: str) -> int:
    """Invalidate cache for a capsule."""
    state = await get_resilience_state()
    if not state.invalidator:
        return 0

    await state.invalidator.on_capsule_updated(capsule_id)
    return 1


async def get_cached_search(query_hash: str) -> Optional[list]:
    """Get search results from cache."""
    state = await get_resilience_state()
    if not state.cache:
        return None

    config = get_resilience_config()
    key = config.cache.search_key_pattern.format(query_hash=query_hash)
    return await state.cache.get(key)


async def cache_search_results(
    query_hash: str,
    results: list,
    ttl: int = 600
) -> bool:
    """Cache search results."""
    state = await get_resilience_state()
    if not state.cache:
        return False

    config = get_resilience_config()
    key = config.cache.search_key_pattern.format(query_hash=query_hash)

    # Extract capsule IDs for invalidation tracking
    capsule_ids = [r.get('id') for r in results if r.get('id')]

    return await state.cache.set(
        key,
        results,
        ttl=ttl,
        query_type="search",
        related_capsule_ids=capsule_ids
    )


async def get_cached_lineage(capsule_id: str, depth: int) -> Optional[dict]:
    """Get lineage from cache."""
    state = await get_resilience_state()
    if not state.cache:
        return None

    config = get_resilience_config()
    key = config.cache.lineage_key_pattern.format(capsule_id=capsule_id, depth=depth)
    return await state.cache.get(key)


async def cache_lineage(
    capsule_id: str,
    depth: int,
    lineage_data: dict,
    ttl: int = 1800
) -> bool:
    """Cache lineage data."""
    state = await get_resilience_state()
    if not state.cache:
        return False

    config = get_resilience_config()
    key = config.cache.lineage_key_pattern.format(capsule_id=capsule_id, depth=depth)

    # Extract all capsule IDs from lineage
    capsule_ids = [capsule_id]
    if 'ancestors' in lineage_data:
        capsule_ids.extend([a.get('id') for a in lineage_data['ancestors'] if a.get('id')])
    if 'descendants' in lineage_data:
        capsule_ids.extend([d.get('id') for d in lineage_data['descendants'] if d.get('id')])

    return await state.cache.set(
        key,
        lineage_data,
        ttl=ttl,
        query_type="lineage",
        related_capsule_ids=capsule_ids
    )


# =============================================================================
# Content Validation Helpers
# =============================================================================

async def validate_capsule_content(
    content: str,
    content_type: str = "text"
) -> ValidationResult:
    """
    Validate capsule content for security threats.

    Returns ValidationResult with any issues found.
    """
    state = await get_resilience_state()
    if not state.validator:
        # Return valid result if validation disabled
        return ValidationResult(
            valid=True,
            threat_level=ThreatLevel.NONE,
        )

    return await state.validator.validate(content, content_type)


def check_content_validation(result: ValidationResult) -> None:
    """
    Check validation result and raise HTTPException if invalid.

    Call this after validate_capsule_content() to enforce validation.
    """
    from fastapi import HTTPException, status

    if not result.valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Content validation failed",
                "threat_level": result.threat_level.value,
                "issues": [
                    {"message": issue.message, "severity": issue.severity.value}
                    for issue in result.issues[:5]  # Limit exposed issues
                ],
            }
        )


# =============================================================================
# Metrics Helpers
# =============================================================================

def record_capsule_created(capsule_type: str) -> None:
    """Record capsule creation metric."""
    metrics = get_metrics()
    metrics.capsule_created(capsule_type)


def record_capsule_updated(capsule_type: str) -> None:
    """Record capsule update metric."""
    metrics = get_metrics()
    metrics.capsule_updated(capsule_type)


def record_capsule_deleted(capsule_type: str) -> None:
    """Record capsule deletion metric."""
    metrics = get_metrics()
    metrics.capsule_deleted(capsule_type)


def record_search(latency: float, result_count: int) -> None:
    """Record search metrics."""
    metrics = get_metrics()
    metrics.search_latency(latency, result_count)


def record_lineage_query(latency: float, depth: int) -> None:
    """Record lineage query metrics."""
    metrics = get_metrics()
    metrics.lineage_query_latency(latency, depth)


def record_cache_hit(cache_type: str = "query") -> None:
    """Record cache hit."""
    metrics = get_metrics()
    metrics.cache_hit(cache_type)


def record_cache_miss(cache_type: str = "query") -> None:
    """Record cache miss."""
    metrics = get_metrics()
    metrics.cache_miss(cache_type)


# =============================================================================
# Governance Caching Helpers
# =============================================================================

async def get_cached_proposal(proposal_id: str) -> Optional[dict]:
    """Get a proposal from cache."""
    state = await get_resilience_state()
    if not state.cache:
        return None

    key = f"proposal:{proposal_id}"
    return await state.cache.get(key)


async def cache_proposal(proposal_id: str, proposal_data: dict, ttl: int = 300) -> bool:
    """Cache a proposal."""
    state = await get_resilience_state()
    if not state.cache:
        return False

    key = f"proposal:{proposal_id}"
    return await state.cache.set(
        key,
        proposal_data,
        ttl=ttl,
        query_type="proposal",
    )


async def invalidate_proposal_cache(proposal_id: str) -> int:
    """Invalidate cache for a proposal."""
    state = await get_resilience_state()
    if not state.cache:
        return 0

    key = f"proposal:{proposal_id}"
    await state.cache.delete(key)

    # Also invalidate proposal list caches
    await state.cache.delete("proposals:list:*")
    await state.cache.delete("proposals:active")
    await state.cache.delete("governance:metrics")
    return 1


async def get_cached_proposals_list(cache_key: str) -> Optional[dict]:
    """Get proposals list from cache."""
    state = await get_resilience_state()
    if not state.cache:
        return None

    return await state.cache.get(f"proposals:list:{cache_key}")


async def cache_proposals_list(cache_key: str, data: dict, ttl: int = 120) -> bool:
    """Cache proposals list."""
    state = await get_resilience_state()
    if not state.cache:
        return False

    return await state.cache.set(
        f"proposals:list:{cache_key}",
        data,
        ttl=ttl,
        query_type="proposals_list",
    )


async def get_cached_governance_metrics() -> Optional[dict]:
    """Get governance metrics from cache."""
    state = await get_resilience_state()
    if not state.cache:
        return None

    return await state.cache.get("governance:metrics")


async def cache_governance_metrics(data: dict, ttl: int = 60) -> bool:
    """Cache governance metrics (short TTL as metrics change frequently)."""
    state = await get_resilience_state()
    if not state.cache:
        return False

    return await state.cache.set(
        "governance:metrics",
        data,
        ttl=ttl,
        query_type="governance_metrics",
    )


# =============================================================================
# Governance Metrics Helpers
# =============================================================================

def record_proposal_created(proposal_type: str) -> None:
    """Record proposal creation metric."""
    metrics = get_metrics()
    metrics.increment("governance_proposals_created", {"type": proposal_type})


def record_vote_cast(vote_choice: str) -> None:
    """Record vote cast metric."""
    metrics = get_metrics()
    metrics.increment("governance_votes_cast", {"choice": vote_choice})


def record_proposal_finalized(status: str) -> None:
    """Record proposal finalization metric."""
    metrics = get_metrics()
    metrics.increment("governance_proposals_finalized", {"status": status})


def record_ghost_council_query(latency: float, use_ai: bool) -> None:
    """Record Ghost Council query metric."""
    metrics = get_metrics()
    metrics.observe("governance_ghost_council_latency", latency, {"ai_enabled": str(use_ai)})


# =============================================================================
# Authentication Metrics Helpers
# =============================================================================

def record_login_attempt(success: bool, reason: str = "") -> None:
    """Record login attempt metric."""
    metrics = get_metrics()
    metrics.increment("auth_login_attempts", {"success": str(success).lower(), "reason": reason})


def record_registration() -> None:
    """Record new user registration metric."""
    metrics = get_metrics()
    metrics.increment("auth_registrations", {})


def record_token_refresh(success: bool) -> None:
    """Record token refresh metric."""
    metrics = get_metrics()
    metrics.increment("auth_token_refreshes", {"success": str(success).lower()})


def record_logout() -> None:
    """Record logout metric."""
    metrics = get_metrics()
    metrics.increment("auth_logouts", {})


def record_password_change() -> None:
    """Record password change metric."""
    metrics = get_metrics()
    metrics.increment("auth_password_changes", {})
