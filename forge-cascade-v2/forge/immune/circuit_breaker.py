"""
Forge Cascade V2 - Circuit Breaker Pattern
Prevents cascade failures by stopping calls to failing services.

States:
- CLOSED: Normal operation, requests pass through
- OPEN: Failure threshold exceeded, requests blocked
- HALF_OPEN: Testing if service recovered

This is part of Forge's Immune System - the self-healing infrastructure
that keeps the digital society resilient.
"""

from __future__ import annotations

import asyncio
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Coroutine, Generic, TypeVar

import structlog

logger = structlog.get_logger(__name__)

T = TypeVar("T")


class CircuitState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"       # Normal - requests flow through
    OPEN = "open"           # Tripped - requests blocked
    HALF_OPEN = "half_open" # Testing - limited requests allowed


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior."""
    
    # Failure thresholds
    failure_threshold: int = 5          # Failures before opening
    failure_rate_threshold: float = 0.5 # 50% failure rate triggers
    
    # Timing
    recovery_timeout: float = 30.0      # Seconds before half-open
    half_open_max_calls: int = 3        # Test calls in half-open state
    
    # Sliding window
    window_size: int = 10               # Calls to track for rate calculation
    min_calls_for_rate: int = 5         # Minimum calls before rate applies
    
    # Success threshold for closing
    success_threshold: int = 2          # Successes in half-open to close
    
    # Timeouts
    call_timeout: float | None = 30.0   # Max seconds for wrapped call
    
    # Exclusions
    excluded_exceptions: tuple[type[Exception], ...] = ()  # Don't count these


@dataclass
class CircuitStats:
    """Statistics for circuit breaker monitoring."""
    
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rejected_calls: int = 0
    timeout_calls: int = 0
    
    # Recent window
    recent_successes: list[float] = field(default_factory=list)
    recent_failures: list[float] = field(default_factory=list)
    
    # State tracking
    state_changes: list[tuple[datetime, CircuitState, CircuitState]] = field(
        default_factory=list
    )
    last_failure_time: float | None = None
    last_success_time: float | None = None
    opened_at: float | None = None
    
    # Half-open tracking
    half_open_successes: int = 0
    half_open_failures: int = 0
    
    def reset_window(self) -> None:
        """Clear the sliding window."""
        self.recent_successes.clear()
        self.recent_failures.clear()
    
    def reset_half_open(self) -> None:
        """Reset half-open counters."""
        self.half_open_successes = 0
        self.half_open_failures = 0
    
    @property
    def failure_rate(self) -> float:
        """Calculate failure rate in recent window."""
        total = len(self.recent_successes) + len(self.recent_failures)
        if total == 0:
            return 0.0
        return len(self.recent_failures) / total
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate in recent window."""
        return 1.0 - self.failure_rate
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for monitoring."""
        return {
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "rejected_calls": self.rejected_calls,
            "timeout_calls": self.timeout_calls,
            "failure_rate": self.failure_rate,
            "success_rate": self.success_rate,
            "last_failure_time": self.last_failure_time,
            "last_success_time": self.last_success_time,
            "state_changes_count": len(self.state_changes),
        }


class CircuitBreakerError(Exception):
    """Raised when circuit is open and call is rejected."""
    
    def __init__(
        self,
        circuit_name: str,
        state: CircuitState,
        recovery_time: float | None = None,
    ):
        self.circuit_name = circuit_name
        self.state = state
        self.recovery_time = recovery_time
        
        msg = f"Circuit '{circuit_name}' is {state.value}"
        if recovery_time:
            msg += f", recovery in {recovery_time:.1f}s"
        super().__init__(msg)


class CircuitBreaker(Generic[T]):
    """
    Circuit Breaker implementation for Forge's Immune System.
    
    Protects against cascade failures by:
    1. Tracking success/failure rates
    2. Opening circuit when threshold exceeded
    3. Gradually testing recovery
    4. Auto-closing when service recovers
    
    Usage:
        breaker = CircuitBreaker("neo4j", config)
        
        # As decorator
        @breaker
        async def query_database():
            ...
        
        # Or direct call
        result = await breaker.call(query_database)
    """
    
    def __init__(
        self,
        name: str,
        config: CircuitBreakerConfig | None = None,
    ):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._stats = CircuitStats()
        self._lock = asyncio.Lock()
        self._listeners: list[Callable[[CircuitState, CircuitState], Coroutine[Any, Any, None]]] = []
        
        logger.info(
            "circuit_breaker_created",
            name=name,
            failure_threshold=self.config.failure_threshold,
            recovery_timeout=self.config.recovery_timeout,
        )
    
    @property
    def state(self) -> CircuitState:
        """Current circuit state."""
        return self._state
    
    @property
    def stats(self) -> CircuitStats:
        """Circuit statistics."""
        return self._stats
    
    @property
    def is_closed(self) -> bool:
        """Check if circuit allows requests."""
        return self._state == CircuitState.CLOSED
    
    @property
    def is_open(self) -> bool:
        """Check if circuit blocks requests."""
        return self._state == CircuitState.OPEN
    
    @property
    def is_half_open(self) -> bool:
        """Check if circuit is testing recovery."""
        return self._state == CircuitState.HALF_OPEN
    
    def add_listener(
        self,
        callback: Callable[[CircuitState, CircuitState], Coroutine[Any, Any, None]],
    ) -> None:
        """Add state change listener."""
        self._listeners.append(callback)
    
    def remove_listener(
        self,
        callback: Callable[[CircuitState, CircuitState], Coroutine[Any, Any, None]],
    ) -> None:
        """Remove state change listener."""
        if callback in self._listeners:
            self._listeners.remove(callback)
    
    async def _notify_listeners(
        self,
        old_state: CircuitState,
        new_state: CircuitState,
    ) -> None:
        """Notify all listeners of state change."""
        for listener in self._listeners:
            try:
                await listener(old_state, new_state)
            except Exception as e:
                logger.warning(
                    "circuit_breaker_listener_error",
                    name=self.name,
                    error=str(e),
                )
    
    async def _set_state(self, new_state: CircuitState) -> None:
        """Change circuit state with logging and notifications."""
        if new_state == self._state:
            return
        
        old_state = self._state
        self._state = new_state
        
        # Track state change
        self._stats.state_changes.append((
            datetime.now(timezone.utc),
            old_state,
            new_state,
        ))
        
        # State-specific actions
        if new_state == CircuitState.OPEN:
            self._stats.opened_at = time.monotonic()
        elif new_state == CircuitState.HALF_OPEN:
            self._stats.reset_half_open()
        elif new_state == CircuitState.CLOSED:
            self._stats.reset_window()
            self._stats.opened_at = None
        
        logger.info(
            "circuit_breaker_state_change",
            name=self.name,
            old_state=old_state.value,
            new_state=new_state.value,
            failure_rate=self._stats.failure_rate,
        )
        
        # Notify listeners
        await self._notify_listeners(old_state, new_state)
    
    def _should_allow_call(self) -> bool:
        """Determine if a call should be allowed through."""
        if self._state == CircuitState.CLOSED:
            return True
        
        if self._state == CircuitState.OPEN:
            # Check if recovery timeout elapsed
            if self._stats.opened_at:
                elapsed = time.monotonic() - self._stats.opened_at
                if elapsed >= self.config.recovery_timeout:
                    return True  # Will transition to half-open
            return False
        
        if self._state == CircuitState.HALF_OPEN:
            # Allow limited calls for testing
            total_half_open = (
                self._stats.half_open_successes +
                self._stats.half_open_failures
            )
            return total_half_open < self.config.half_open_max_calls
        
        return False
    
    def _get_recovery_time(self) -> float | None:
        """Get time remaining until recovery attempt."""
        if self._state != CircuitState.OPEN:
            return None
        
        if self._stats.opened_at is None:
            return None
        
        elapsed = time.monotonic() - self._stats.opened_at
        remaining = self.config.recovery_timeout - elapsed
        return max(0, remaining)
    
    async def _record_success(self) -> None:
        """Record a successful call."""
        now = time.monotonic()
        self._stats.total_calls += 1
        self._stats.successful_calls += 1
        self._stats.last_success_time = now
        
        if self._state == CircuitState.CLOSED:
            self._stats.recent_successes.append(now)
            self._trim_window()
        
        elif self._state == CircuitState.HALF_OPEN:
            self._stats.half_open_successes += 1
            
            # Check if we can close circuit
            if self._stats.half_open_successes >= self.config.success_threshold:
                await self._set_state(CircuitState.CLOSED)
    
    async def _record_failure(self, exception: Exception) -> None:
        """Record a failed call."""
        now = time.monotonic()
        self._stats.total_calls += 1
        self._stats.failed_calls += 1
        self._stats.last_failure_time = now
        
        if self._state == CircuitState.CLOSED:
            self._stats.recent_failures.append(now)
            self._trim_window()
            
            # Check failure threshold
            if await self._should_open():
                await self._set_state(CircuitState.OPEN)
        
        elif self._state == CircuitState.HALF_OPEN:
            self._stats.half_open_failures += 1
            # Any failure in half-open reopens circuit
            await self._set_state(CircuitState.OPEN)
    
    def _trim_window(self) -> None:
        """Trim sliding window to configured size."""
        window_size = self.config.window_size
        
        # Keep only most recent
        while len(self._stats.recent_successes) + len(self._stats.recent_failures) > window_size:
            # Remove oldest (from whichever list has older entry)
            if not self._stats.recent_successes:
                self._stats.recent_failures.pop(0)
            elif not self._stats.recent_failures:
                self._stats.recent_successes.pop(0)
            elif self._stats.recent_successes[0] < self._stats.recent_failures[0]:
                self._stats.recent_successes.pop(0)
            else:
                self._stats.recent_failures.pop(0)
    
    async def _should_open(self) -> bool:
        """Determine if circuit should open based on failures."""
        # Check absolute failure count
        failures = len(self._stats.recent_failures)
        if failures >= self.config.failure_threshold:
            logger.warning(
                "circuit_breaker_failure_threshold",
                name=self.name,
                failures=failures,
                threshold=self.config.failure_threshold,
            )
            return True
        
        # Check failure rate (if enough calls)
        total = len(self._stats.recent_successes) + len(self._stats.recent_failures)
        if total >= self.config.min_calls_for_rate:
            rate = self._stats.failure_rate
            if rate >= self.config.failure_rate_threshold:
                logger.warning(
                    "circuit_breaker_rate_threshold",
                    name=self.name,
                    failure_rate=rate,
                    threshold=self.config.failure_rate_threshold,
                )
                return True
        
        return False
    
    async def call(
        self,
        func: Callable[..., Coroutine[Any, Any, T]],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """
        Execute a function through the circuit breaker.
        
        Args:
            func: Async function to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func
            
        Returns:
            Result from func
            
        Raises:
            CircuitBreakerError: If circuit is open
            TimeoutError: If call exceeds timeout
            Exception: Any exception from func (also recorded as failure)
        """
        async with self._lock:
            # Check if we should transition to half-open
            if self._state == CircuitState.OPEN:
                if self._stats.opened_at:
                    elapsed = time.monotonic() - self._stats.opened_at
                    if elapsed >= self.config.recovery_timeout:
                        await self._set_state(CircuitState.HALF_OPEN)
            
            # Check if call is allowed
            if not self._should_allow_call():
                self._stats.rejected_calls += 1
                raise CircuitBreakerError(
                    self.name,
                    self._state,
                    self._get_recovery_time(),
                )
        
        # Execute call
        try:
            if self.config.call_timeout:
                result = await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=self.config.call_timeout,
                )
            else:
                result = await func(*args, **kwargs)
            
            async with self._lock:
                await self._record_success()
            
            return result
        
        except asyncio.TimeoutError:
            async with self._lock:
                self._stats.timeout_calls += 1
                await self._record_failure(TimeoutError("Call timed out"))
            raise
        
        except Exception as e:
            # Check if exception should be excluded
            if isinstance(e, self.config.excluded_exceptions):
                async with self._lock:
                    await self._record_success()
                raise
            
            async with self._lock:
                await self._record_failure(e)
            raise
    
    def __call__(
        self,
        func: Callable[..., Coroutine[Any, Any, T]],
    ) -> Callable[..., Coroutine[Any, Any, T]]:
        """Decorator syntax for circuit breaker."""
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            return await self.call(func, *args, **kwargs)
        
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper
    
    async def reset(self) -> None:
        """Manually reset circuit to closed state."""
        async with self._lock:
            self._stats = CircuitStats()
            await self._set_state(CircuitState.CLOSED)
        
        logger.info("circuit_breaker_reset", name=self.name)
    
    async def force_open(self, duration: float | None = None) -> None:
        """Manually open circuit (for testing/maintenance)."""
        async with self._lock:
            await self._set_state(CircuitState.OPEN)
            self._stats.opened_at = time.monotonic()
            
            # Override recovery timeout if specified
            if duration:
                self.config.recovery_timeout = duration
        
        logger.info(
            "circuit_breaker_forced_open",
            name=self.name,
            duration=duration,
        )
    
    def get_status(self) -> dict[str, Any]:
        """Get current circuit breaker status."""
        return {
            "name": self.name,
            "state": self._state.value,
            "stats": self._stats.to_dict(),
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "failure_rate_threshold": self.config.failure_rate_threshold,
                "recovery_timeout": self.config.recovery_timeout,
                "call_timeout": self.config.call_timeout,
            },
            "recovery_time": self._get_recovery_time(),
        }


class CircuitBreakerRegistry:
    """
    Registry for managing multiple circuit breakers.
    
    Provides centralized access and monitoring for all circuits
    in the Forge system.
    """
    
    def __init__(self):
        self._breakers: dict[str, CircuitBreaker] = {}
        self._lock = asyncio.Lock()
    
    async def get_or_create(
        self,
        name: str,
        config: CircuitBreakerConfig | None = None,
    ) -> CircuitBreaker:
        """Get existing or create new circuit breaker."""
        async with self._lock:
            if name not in self._breakers:
                self._breakers[name] = CircuitBreaker(name, config)
            return self._breakers[name]
    
    async def get(self, name: str) -> CircuitBreaker | None:
        """Get circuit breaker by name."""
        return self._breakers.get(name)
    
    async def remove(self, name: str) -> bool:
        """Remove circuit breaker."""
        async with self._lock:
            if name in self._breakers:
                del self._breakers[name]
                return True
            return False
    
    def list_all(self) -> list[str]:
        """List all circuit breaker names."""
        return list(self._breakers.keys())
    
    def get_all_status(self) -> dict[str, dict[str, Any]]:
        """Get status of all circuit breakers."""
        return {
            name: breaker.get_status()
            for name, breaker in self._breakers.items()
        }
    
    async def reset_all(self) -> None:
        """Reset all circuit breakers."""
        for breaker in self._breakers.values():
            await breaker.reset()
    
    def get_open_circuits(self) -> list[str]:
        """Get list of currently open circuits."""
        return [
            name for name, breaker in self._breakers.items()
            if breaker.is_open
        ]
    
    def get_health_summary(self) -> dict[str, Any]:
        """Get health summary for all circuits."""
        total = len(self._breakers)
        open_count = len(self.get_open_circuits())
        half_open = sum(1 for b in self._breakers.values() if b.is_half_open)
        closed = total - open_count - half_open
        
        return {
            "total_circuits": total,
            "closed": closed,
            "open": open_count,
            "half_open": half_open,
            "health_score": closed / total if total > 0 else 1.0,
            "open_circuits": self.get_open_circuits(),
        }


# Global registry for convenience - uses double-checked locking for thread safety
_global_registry: CircuitBreakerRegistry | None = None
_registry_lock = threading.Lock()


def get_circuit_registry() -> CircuitBreakerRegistry:
    """
    Get global circuit breaker registry.

    Thread-safe using double-checked locking pattern.
    """
    global _global_registry
    if _global_registry is None:
        with _registry_lock:
            # Double-check after acquiring lock
            if _global_registry is None:
                _global_registry = CircuitBreakerRegistry()
    return _global_registry


async def circuit_breaker(
    name: str,
    config: CircuitBreakerConfig | None = None,
) -> CircuitBreaker:
    """Get or create a circuit breaker from global registry."""
    return await get_circuit_registry().get_or_create(name, config)


# Pre-configured circuit breakers for common Forge services
class ForgeCircuits:
    """Pre-configured circuit breakers for Forge services."""
    
    @staticmethod
    async def neo4j() -> CircuitBreaker:
        """Circuit breaker for Neo4j database."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=30.0,
            call_timeout=10.0,
        )
        return await circuit_breaker("neo4j", config)
    
    @staticmethod
    async def external_ml() -> CircuitBreaker:
        """Circuit breaker for external ML services."""
        config = CircuitBreakerConfig(
            failure_threshold=5,
            recovery_timeout=60.0,
            call_timeout=30.0,
        )
        return await circuit_breaker("external_ml", config)
    
    @staticmethod
    async def overlay(overlay_name: str) -> CircuitBreaker:
        """Circuit breaker for specific overlay."""
        config = CircuitBreakerConfig(
            failure_threshold=5,
            recovery_timeout=15.0,
            call_timeout=5.0,
        )
        return await circuit_breaker(f"overlay_{overlay_name}", config)
    
    @staticmethod
    async def webhook() -> CircuitBreaker:
        """Circuit breaker for webhook calls."""
        config = CircuitBreakerConfig(
            failure_threshold=10,
            recovery_timeout=120.0,
            call_timeout=15.0,
            failure_rate_threshold=0.7,  # More tolerant
        )
        return await circuit_breaker("webhook", config)


__all__ = [
    "CircuitState",
    "CircuitBreakerConfig",
    "CircuitStats",
    "CircuitBreakerError",
    "CircuitBreaker",
    "CircuitBreakerRegistry",
    "get_circuit_registry",
    "circuit_breaker",
    "ForgeCircuits",
]
