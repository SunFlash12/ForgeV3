#!/usr/bin/env python3
"""
Verify System - Startup Validation Script

Verifies that all Forge system components are operational before use.
Run this after starting the system to confirm everything is working.

USAGE:
    python scripts/verify_system.py

    # With custom URLs:
    BACKEND_URL=http://localhost:8001 FRONTEND_URL=http://localhost:5173 python scripts/verify_system.py

EXIT CODES:
    0 - All checks passed
    1 - One or more checks failed

SECURITY:
    - Does not expose any credentials
    - Only reads public health endpoints
    - Safe to run in any environment
"""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Any

# Try to import httpx, fall back to instructions if not installed
try:
    import httpx
except ImportError:
    print("Error: httpx is required. Install with: pip install httpx")
    sys.exit(1)


# Configuration from environment variables (no hardcoded secrets)
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8001")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173")
TIMEOUT = float(os.environ.get("VERIFY_TIMEOUT", "10"))


class CheckResult:
    """Result of a system check."""

    def __init__(self, name: str, passed: bool, details: str = ""):
        self.name = name
        self.passed = passed
        self.details = details


async def check_backend_health() -> CheckResult:
    """Check if backend is reachable and healthy."""
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(f"{BACKEND_URL}/health")
            if response.status_code == 200:
                data = response.json()
                status = data.get("status", "unknown")
                if status in ("healthy", "starting"):
                    return CheckResult("Backend Health", True, f"Status: {status}")
                return CheckResult("Backend Health", False, f"Status: {status}")
            return CheckResult(
                "Backend Health", False, f"HTTP {response.status_code}"
            )
    except httpx.ConnectError:
        return CheckResult("Backend Health", False, "Connection refused")
    except httpx.TimeoutException:
        return CheckResult("Backend Health", False, "Timeout")
    except Exception as e:
        return CheckResult("Backend Health", False, str(e)[:50])


async def check_backend_detailed() -> tuple[CheckResult, dict[str, Any]]:
    """Check detailed backend health including component status."""
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(f"{BACKEND_URL}/health/detailed")
            if response.status_code == 200:
                data = response.json()
                status = data.get("status", "unknown")
                warnings = data.get("warnings", [])

                if status == "healthy":
                    return CheckResult(
                        "Backend Detailed", True, f"Status: {status}"
                    ), data
                elif status == "degraded":
                    return CheckResult(
                        "Backend Detailed",
                        True,  # Degraded is still "working"
                        f"Status: {status}, Warnings: {len(warnings)}",
                    ), data
                else:
                    return CheckResult(
                        "Backend Detailed", False, f"Status: {status}"
                    ), data
            return CheckResult(
                "Backend Detailed", False, f"HTTP {response.status_code}"
            ), {}
    except httpx.ConnectError:
        return CheckResult("Backend Detailed", False, "Connection refused"), {}
    except httpx.TimeoutException:
        return CheckResult("Backend Detailed", False, "Timeout"), {}
    except Exception as e:
        return CheckResult("Backend Detailed", False, str(e)[:50]), {}


async def check_database(detailed_data: dict[str, Any]) -> CheckResult:
    """Check database connectivity from detailed health data."""
    components = detailed_data.get("components", {})
    db = components.get("database", {})

    if db.get("connected"):
        latency = db.get("latency_ms", "?")
        return CheckResult("Neo4j Database", True, f"Latency: {latency}ms")
    else:
        error = db.get("error", "Not connected")
        return CheckResult("Neo4j Database", False, error[:50])


async def check_llm_provider(detailed_data: dict[str, Any]) -> CheckResult:
    """Check LLM provider status - warns if mock."""
    components = detailed_data.get("components", {})
    llm = components.get("llm_provider", {})

    provider = llm.get("provider", "unknown")
    is_mock = llm.get("is_mock", True)
    operational = llm.get("operational", False)

    if not operational:
        return CheckResult("LLM Provider", False, "Not operational")
    elif is_mock:
        return CheckResult(
            "LLM Provider", True, f"MOCK (AI features limited)"
        )
    else:
        return CheckResult("LLM Provider", True, f"Provider: {provider}")


async def check_embedding_provider(detailed_data: dict[str, Any]) -> CheckResult:
    """Check embedding provider status - warns if mock."""
    components = detailed_data.get("components", {})
    emb = components.get("embedding_provider", {})

    provider = emb.get("provider", "unknown")
    is_mock = emb.get("is_mock", True)
    dimensions = emb.get("dimensions")

    if is_mock:
        return CheckResult(
            "Embedding Provider", True, f"MOCK (search degraded)"
        )
    else:
        return CheckResult(
            "Embedding Provider", True, f"{provider} ({dimensions}d)"
        )


async def check_frontend() -> CheckResult:
    """Check if frontend is reachable."""
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(FRONTEND_URL)
            if response.status_code == 200:
                return CheckResult("Frontend", True, "Reachable")
            return CheckResult("Frontend", False, f"HTTP {response.status_code}")
    except httpx.ConnectError:
        return CheckResult("Frontend", False, "Connection refused")
    except httpx.TimeoutException:
        return CheckResult("Frontend", False, "Timeout")
    except Exception as e:
        return CheckResult("Frontend", False, str(e)[:50])


def print_result(result: CheckResult) -> None:
    """Print a check result with color coding."""
    symbol = "\033[92m✓\033[0m" if result.passed else "\033[91m✗\033[0m"
    details = f" ({result.details})" if result.details else ""
    print(f"  {symbol} {result.name}{details}")


def print_warning(message: str) -> None:
    """Print a warning message."""
    print(f"  \033[93m⚠\033[0m {message}")


async def main() -> int:
    """Run all system verification checks."""
    print("\n\033[1m=== Forge System Verification ===\033[0m\n")
    print(f"Backend URL:  {BACKEND_URL}")
    print(f"Frontend URL: {FRONTEND_URL}")
    print()

    results: list[CheckResult] = []
    warnings: list[str] = []

    # Check backend health (basic)
    result = await check_backend_health()
    results.append(result)
    print_result(result)

    # Check backend detailed health
    detailed_result, detailed_data = await check_backend_detailed()
    results.append(detailed_result)
    print_result(detailed_result)

    if detailed_data:
        # Extract warnings from detailed response
        warnings.extend(detailed_data.get("warnings", []))

        # Check database
        db_result = await check_database(detailed_data)
        results.append(db_result)
        print_result(db_result)

        # Check LLM provider
        llm_result = await check_llm_provider(detailed_data)
        results.append(llm_result)
        print_result(llm_result)

        # Check embedding provider
        emb_result = await check_embedding_provider(detailed_data)
        results.append(emb_result)
        print_result(emb_result)

    # Check frontend
    frontend_result = await check_frontend()
    results.append(frontend_result)
    print_result(frontend_result)

    # Print warnings
    if warnings:
        print("\n\033[1mWarnings:\033[0m")
        for warning in warnings:
            print_warning(warning)

    # Summary
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    all_passed = passed == total

    print()
    if all_passed:
        print(f"\033[92m✓ All {total} checks passed\033[0m")
    else:
        print(f"\033[91m✗ {total - passed} of {total} checks failed\033[0m")

    print()
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
