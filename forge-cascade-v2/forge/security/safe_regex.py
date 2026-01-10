"""
Safe Regex Utilities for Forge Cascade V2

SECURITY FIX (Audit 3): Provides regex utilities with:
- ReDoS (Regular Expression Denial of Service) protection
- Pattern complexity limits
- Timeout-based execution
- Pattern validation

Use these functions instead of raw re.match/search/findall when processing
untrusted input to prevent ReDoS attacks.
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from functools import lru_cache
from re import Pattern
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# Maximum allowed pattern length
MAX_PATTERN_LENGTH = 500

# Maximum allowed input length for regex operations
MAX_INPUT_LENGTH = 100000  # 100KB

# Default timeout for regex operations (seconds)
DEFAULT_REGEX_TIMEOUT = 1.0

# Patterns that indicate potential ReDoS vulnerability
# These are patterns known to cause catastrophic backtracking
REDOS_SUSPICIOUS_PATTERNS = [
    r'\(.*\+.*\)\+',           # Nested quantifiers like (a+)+
    r'\(.*\*.*\)\*',           # Nested quantifiers like (a*)*
    r'\(.*\+.*\)\*',           # Mixed nested quantifiers
    r'\(.*\*.*\)\+',           # Mixed nested quantifiers
    r'\(.*\{.*\}.*\)\{',       # Nested counted quantifiers
    r'\(.*\|.*\)\+',           # Alternation with quantifier
    r'\(.*\|.*\)\*',           # Alternation with quantifier
    r'\.[\*\+]\.\*',           # Overlapping wildcards
    r'\[.*\][\*\+]\[.*\][\*\+]',  # Adjacent character classes with quantifiers
]

# Thread pool for timeout execution
_executor: ThreadPoolExecutor | None = None


def _get_executor() -> ThreadPoolExecutor:
    """Get or create the thread pool executor."""
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="regex_worker")
    return _executor


class RegexValidationError(Exception):
    """Raised when a regex pattern fails validation."""
    pass


class RegexTimeoutError(Exception):
    """Raised when a regex operation times out."""
    pass


def validate_pattern(pattern: str) -> tuple[bool, str | None]:
    """
    Validate a regex pattern for safety.

    Args:
        pattern: The regex pattern to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check length
    if len(pattern) > MAX_PATTERN_LENGTH:
        return False, f"Pattern length ({len(pattern)}) exceeds maximum ({MAX_PATTERN_LENGTH})"

    # Check for empty pattern
    if not pattern or pattern.isspace():
        return False, "Pattern cannot be empty"

    # Check for ReDoS suspicious patterns
    for suspicious in REDOS_SUSPICIOUS_PATTERNS:
        try:
            if re.search(suspicious, pattern):
                return False, "Pattern contains potentially vulnerable construct"
        except re.error:
            pass

    # Try to compile the pattern
    try:
        re.compile(pattern)
    except re.error as e:
        return False, f"Invalid regex pattern: {e}"

    return True, None


@lru_cache(maxsize=1000)
def _compile_pattern_cached(pattern: str, flags: int = 0) -> Pattern:
    """Cache compiled patterns to avoid recompilation."""
    return re.compile(pattern, flags)


def safe_compile(pattern: str, flags: int = 0, validate: bool = True) -> Pattern:
    """
    Safely compile a regex pattern with validation.

    Args:
        pattern: The regex pattern to compile
        flags: Regex flags (re.IGNORECASE, etc.)
        validate: Whether to validate pattern for ReDoS vulnerability

    Returns:
        Compiled pattern

    Raises:
        RegexValidationError: If pattern is invalid or unsafe
    """
    if validate:
        is_valid, error = validate_pattern(pattern)
        if not is_valid:
            raise RegexValidationError(error)

    try:
        return _compile_pattern_cached(pattern, flags)
    except re.error as e:
        raise RegexValidationError(f"Failed to compile pattern: {e}")


def _run_with_timeout(func, *args, timeout: float = DEFAULT_REGEX_TIMEOUT) -> Any:
    """
    Run a function with a timeout.

    Args:
        func: Function to run
        *args: Arguments to pass to function
        timeout: Timeout in seconds

    Returns:
        Function result

    Raises:
        RegexTimeoutError: If operation times out
    """
    executor = _get_executor()
    future = executor.submit(func, *args)
    try:
        return future.result(timeout=timeout)
    except FuturesTimeoutError:
        # Note: The thread may continue running, but we limit damage via input size
        raise RegexTimeoutError(f"Regex operation timed out after {timeout}s")


def safe_match(
    pattern: str,
    string: str,
    flags: int = 0,
    timeout: float = DEFAULT_REGEX_TIMEOUT,
    validate: bool = True
) -> re.Match | None:
    """
    Safely perform re.match with timeout and validation.

    Args:
        pattern: Regex pattern
        string: String to match
        flags: Regex flags
        timeout: Operation timeout in seconds
        validate: Whether to validate pattern

    Returns:
        Match object or None

    Raises:
        RegexValidationError: If pattern is unsafe
        RegexTimeoutError: If operation times out
    """
    # Limit input size
    if len(string) > MAX_INPUT_LENGTH:
        original_length = len(string)
        string = string[:MAX_INPUT_LENGTH]
        logger.warning("regex_input_truncated", original_length=original_length, max_length=MAX_INPUT_LENGTH)

    compiled = safe_compile(pattern, flags, validate)
    return _run_with_timeout(compiled.match, string, timeout=timeout)


def safe_search(
    pattern: str,
    string: str,
    flags: int = 0,
    timeout: float = DEFAULT_REGEX_TIMEOUT,
    validate: bool = True
) -> re.Match | None:
    """
    Safely perform re.search with timeout and validation.

    Args:
        pattern: Regex pattern
        string: String to search
        flags: Regex flags
        timeout: Operation timeout in seconds
        validate: Whether to validate pattern

    Returns:
        Match object or None

    Raises:
        RegexValidationError: If pattern is unsafe
        RegexTimeoutError: If operation times out
    """
    # Limit input size
    if len(string) > MAX_INPUT_LENGTH:
        original_length = len(string)
        string = string[:MAX_INPUT_LENGTH]
        logger.warning("regex_input_truncated", original_length=original_length, max_length=MAX_INPUT_LENGTH)

    compiled = safe_compile(pattern, flags, validate)
    return _run_with_timeout(compiled.search, string, timeout=timeout)


def safe_findall(
    pattern: str,
    string: str,
    flags: int = 0,
    timeout: float = DEFAULT_REGEX_TIMEOUT,
    validate: bool = True,
    max_results: int = 1000
) -> list:
    """
    Safely perform re.findall with timeout and validation.

    Args:
        pattern: Regex pattern
        string: String to search
        flags: Regex flags
        timeout: Operation timeout in seconds
        validate: Whether to validate pattern
        max_results: Maximum number of results to return

    Returns:
        List of matches (limited to max_results)

    Raises:
        RegexValidationError: If pattern is unsafe
        RegexTimeoutError: If operation times out
    """
    # Limit input size
    if len(string) > MAX_INPUT_LENGTH:
        original_length = len(string)
        string = string[:MAX_INPUT_LENGTH]
        logger.warning("regex_input_truncated", original_length=original_length, max_length=MAX_INPUT_LENGTH)

    compiled = safe_compile(pattern, flags, validate)
    results = _run_with_timeout(compiled.findall, string, timeout=timeout)

    # Limit result count
    if len(results) > max_results:
        logger.warning("regex_results_truncated", original_count=len(results), max_results=max_results)
        return results[:max_results]

    return results


def safe_sub(
    pattern: str,
    repl: str,
    string: str,
    count: int = 0,
    flags: int = 0,
    timeout: float = DEFAULT_REGEX_TIMEOUT,
    validate: bool = True
) -> str:
    """
    Safely perform re.sub with timeout and validation.

    Args:
        pattern: Regex pattern
        repl: Replacement string
        string: String to process
        count: Max replacements (0 = all)
        flags: Regex flags
        timeout: Operation timeout in seconds
        validate: Whether to validate pattern

    Returns:
        String with replacements

    Raises:
        RegexValidationError: If pattern is unsafe
        RegexTimeoutError: If operation times out
    """
    # Limit input size
    if len(string) > MAX_INPUT_LENGTH:
        original_length = len(string)
        string = string[:MAX_INPUT_LENGTH]
        logger.warning("regex_input_truncated", original_length=original_length, max_length=MAX_INPUT_LENGTH)

    compiled = safe_compile(pattern, flags, validate)
    return _run_with_timeout(compiled.sub, repl, string, count, timeout=timeout)


def shutdown_executor() -> None:
    """Shutdown the regex thread pool executor."""
    global _executor
    if _executor is not None:
        _executor.shutdown(wait=False)
        _executor = None
