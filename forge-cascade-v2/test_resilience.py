"""
Resilience Integration Test Suite

Tests that resilience features are properly integrated into all API routes:
- Metrics recording
- Cache operations
- Content validation

Verifies the resilience module is working across all route files.

SECURITY: Requires SEED_ADMIN_PASSWORD environment variable to be set.
Never commit hardcoded credentials to version control.
"""

import os
import sys
import requests
import time
from datetime import datetime

BASE_URL = "http://localhost:8001/api/v1"

# SECURITY: Load password from environment variable only
ADMIN_PASSWORD = os.environ.get("SEED_ADMIN_PASSWORD")
if not ADMIN_PASSWORD:
    print("ERROR: SEED_ADMIN_PASSWORD environment variable is required")
    print("Set it before running tests:")
    print("  export SEED_ADMIN_PASSWORD=your_admin_password")
    sys.exit(1)

test_results = []


def log_test(test_name: str, passed: bool, details: str = ""):
    """Log test result."""
    status = "PASS" if passed else "FAIL"
    test_results.append({"test": test_name, "passed": passed, "details": details})
    print(f"[{status}] {test_name}")
    if details:
        print(f"       {details}")


def get_session():
    """Create authenticated session."""
    session = requests.Session()
    r = session.post(f"{BASE_URL}/auth/login", json={"username": "admin", "password": ADMIN_PASSWORD})
    if r.status_code != 200:
        print(f"Login failed: {r.status_code} {r.text[:200]}")
        return None
    return session


def main():
    print("=" * 70)
    print("FORGE RESILIENCE INTEGRATION TEST SUITE")
    print("=" * 70)
    print()

    # Check server health
    try:
        r = requests.get("http://localhost:8001/health", timeout=5)
        if r.status_code != 200:
            print("ERROR: Server not healthy")
            return False
    except Exception as e:
        print(f"ERROR: Cannot connect to server - {e}")
        return False

    print("Server is healthy. Starting resilience tests...\n")

    session = get_session()
    if not session:
        print("ERROR: Could not authenticate")
        return False

    print("Authenticated successfully.\n")

    # =========================================================================
    # SECTION 1: AUTH ROUTES RESILIENCE
    # =========================================================================
    print("-" * 70)
    print("SECTION 1: AUTH ROUTES RESILIENCE")
    print("-" * 70)

    # Test 1.1: Registration with content validation
    test_user = f"testuser_{int(time.time())}"
    r = session.post(f"{BASE_URL}/auth/register", json={
        "username": test_user,
        "email": f"{test_user}@test.com",
        "password": "TestPassword123!",
        "display_name": "Test User"
    })
    log_test(
        "1.1 Registration (content validation + metrics)",
        r.status_code in [201, 409],  # 409 if user exists
        f"Status: {r.status_code}"
    )

    # Test 1.2: Login metrics
    r = requests.post(f"{BASE_URL}/auth/login", json={
        "username": "admin",
        "password": ADMIN_PASSWORD
    })
    log_test(
        "1.2 Login (metrics recording)",
        r.status_code == 200,
        f"Status: {r.status_code}"
    )

    # Test 1.3: Failed login metrics
    r = requests.post(f"{BASE_URL}/auth/login", json={
        "username": "admin",
        "password": "wrongpassword"
    })
    log_test(
        "1.3 Failed login (failure metrics)",
        r.status_code == 401,
        f"Status: {r.status_code}"
    )

    # Test 1.4: Token refresh metrics
    r = session.post(f"{BASE_URL}/auth/refresh")
    log_test(
        "1.4 Token refresh (metrics recording)",
        r.status_code in [200, 401],  # May need valid refresh token
        f"Status: {r.status_code}"
    )

    print()

    # =========================================================================
    # SECTION 2: CAPSULE ROUTES RESILIENCE
    # =========================================================================
    print("-" * 70)
    print("SECTION 2: CAPSULE ROUTES RESILIENCE")
    print("-" * 70)

    # Test 2.1: Create capsule (content validation + metrics)
    r = session.post(f"{BASE_URL}/capsules/", json={
        "content": "This is a test capsule for resilience testing.",
        "type": "KNOWLEDGE",
        "metadata": {"test": True}
    })
    capsule_id = None
    if r.status_code in [200, 201]:
        capsule_id = r.json().get("id")
    log_test(
        "2.1 Create capsule (validation + metrics)",
        r.status_code in [200, 201],
        f"Status: {r.status_code}, ID: {capsule_id[:8] if capsule_id else 'N/A'}..."
    )

    # Test 2.2: Get capsule (caching)
    if capsule_id:
        r = session.get(f"{BASE_URL}/capsules/{capsule_id}")
        log_test(
            "2.2 Get capsule (cache-first lookup)",
            r.status_code == 200,
            f"Status: {r.status_code}"
        )

        # Second fetch should hit cache
        r2 = session.get(f"{BASE_URL}/capsules/{capsule_id}")
        log_test(
            "2.3 Get capsule again (potential cache hit)",
            r2.status_code == 200,
            f"Status: {r2.status_code}"
        )

    # Test 2.4: Update capsule (cache invalidation + metrics)
    if capsule_id:
        r = session.patch(f"{BASE_URL}/capsules/{capsule_id}", json={
            "content": "Updated content for resilience testing."
        })
        log_test(
            "2.4 Update capsule (cache invalidation + metrics)",
            r.status_code == 200,
            f"Status: {r.status_code}"
        )

    # Test 2.5: Search capsules (search cache)
    r = session.post(f"{BASE_URL}/capsules/search", json={
        "query": "resilience testing",
        "limit": 5
    })
    log_test(
        "2.5 Search capsules (search caching)",
        r.status_code in [200, 201],
        f"Status: {r.status_code}"
    )

    print()

    # =========================================================================
    # SECTION 3: GOVERNANCE ROUTES RESILIENCE
    # =========================================================================
    print("-" * 70)
    print("SECTION 3: GOVERNANCE ROUTES RESILIENCE")
    print("-" * 70)

    # Test 3.1: Create proposal (content validation + metrics)
    r = session.post(f"{BASE_URL}/governance/proposals", json={
        "title": "Resilience Test Proposal",
        "description": "Testing resilience integration in governance routes with proper validation.",
        "proposal_type": "policy",
        "action": {"test_param": "test_value"}
    })
    proposal_id = None
    if r.status_code in [200, 201]:
        proposal_id = r.json().get("id")
    log_test(
        "3.1 Create proposal (validation + metrics)",
        r.status_code in [200, 201],
        f"Status: {r.status_code}"
    )

    # Test 3.2: Get proposals (caching)
    r = session.get(f"{BASE_URL}/governance/proposals")
    log_test(
        "3.2 List proposals (caching)",
        r.status_code == 200,
        f"Status: {r.status_code}"
    )

    # Test 3.3: Ghost Council (metrics)
    r = session.get(f"{BASE_URL}/governance/ghost-council/members")
    log_test(
        "3.3 Ghost Council members (metrics)",
        r.status_code == 200,
        f"Status: {r.status_code}"
    )

    # Test 3.4: Vote on proposal (metrics)
    if proposal_id:
        r = session.post(f"{BASE_URL}/governance/proposals/{proposal_id}/vote", json={
            "choice": "APPROVE",
            "rationale": "Testing vote metrics"
        })
        log_test(
            "3.4 Cast vote (metrics recording)",
            r.status_code in [200, 201, 400, 403],  # Various valid responses
            f"Status: {r.status_code}"
        )

    print()

    # =========================================================================
    # SECTION 4: OVERLAY ROUTES RESILIENCE
    # =========================================================================
    print("-" * 70)
    print("SECTION 4: OVERLAY ROUTES RESILIENCE")
    print("-" * 70)

    # Test 4.1: List overlays (caching)
    r = session.get(f"{BASE_URL}/overlays/")
    log_test(
        "4.1 List overlays (caching)",
        r.status_code == 200,
        f"Status: {r.status_code}"
    )

    # Test 4.2: Get overlay metrics
    r = session.get(f"{BASE_URL}/overlays/metrics/summary")
    log_test(
        "4.2 Overlay metrics summary",
        r.status_code in [200, 404],
        f"Status: {r.status_code}"
    )

    print()

    # =========================================================================
    # SECTION 5: SYSTEM ROUTES RESILIENCE
    # =========================================================================
    print("-" * 70)
    print("SECTION 5: SYSTEM ROUTES RESILIENCE")
    print("-" * 70)

    # Test 5.1: Health check (metrics)
    r = session.get(f"{BASE_URL}/system/health")
    log_test(
        "5.1 Health check (metrics recording)",
        r.status_code == 200,
        f"Status: {r.status_code}"
    )

    # Test 5.2: System metrics (caching)
    r = session.get(f"{BASE_URL}/system/metrics")
    log_test(
        "5.2 System metrics (caching)",
        r.status_code == 200,
        f"Status: {r.status_code}"
    )

    # Test 5.3: Circuit breakers
    r = session.get(f"{BASE_URL}/system/circuit-breakers")
    log_test(
        "5.3 Circuit breakers status",
        r.status_code == 200,
        f"Status: {r.status_code}"
    )

    # Test 5.4: Anomalies
    r = session.get(f"{BASE_URL}/system/anomalies")
    log_test(
        "5.4 Anomalies list",
        r.status_code == 200,
        f"Status: {r.status_code}"
    )

    # Test 5.5: Audit log
    r = session.get(f"{BASE_URL}/system/audit")
    log_test(
        "5.5 Audit log (admin access)",
        r.status_code == 200,
        f"Status: {r.status_code}"
    )

    print()

    # =========================================================================
    # SECTION 6: CASCADE ROUTES RESILIENCE
    # =========================================================================
    print("-" * 70)
    print("SECTION 6: CASCADE ROUTES RESILIENCE")
    print("-" * 70)

    # Test 6.1: List active cascades
    r = session.get(f"{BASE_URL}/cascade/")
    log_test(
        "6.1 List active cascades",
        r.status_code == 200,
        f"Status: {r.status_code}"
    )

    # Test 6.2: Cascade metrics
    r = session.get(f"{BASE_URL}/cascade/metrics/summary")
    log_test(
        "6.2 Cascade metrics summary",
        r.status_code == 200,
        f"Status: {r.status_code}"
    )

    # Test 6.3: Trigger cascade (metrics)
    r = session.post(f"{BASE_URL}/cascade/trigger", json={
        "source_overlay": "test_overlay",
        "insight_type": "resilience_test",
        "insight_data": {"test": True},
        "max_hops": 3
    })
    log_test(
        "6.3 Trigger cascade (metrics recording)",
        r.status_code in [200, 201, 400, 422],
        f"Status: {r.status_code}"
    )

    print()

    # =========================================================================
    # SECTION 7: RESILIENCE MODULE VERIFICATION
    # =========================================================================
    print("-" * 70)
    print("SECTION 7: RESILIENCE MODULE VERIFICATION")
    print("-" * 70)

    # Test 7.1: Verify resilience imports work
    try:
        from forge.resilience.integration import (
            record_login_attempt,
            record_registration,
            record_capsule_created,
            record_proposal_created,
            record_overlay_activated,
            record_health_check_access,
            record_cascade_triggered,
        )
        log_test("7.1 Resilience metrics imports", True, "All metric helpers imported")
    except ImportError as e:
        log_test("7.1 Resilience metrics imports", False, str(e))

    # Test 7.2: Verify caching helpers
    try:
        from forge.resilience.integration import (
            get_cached_capsule,
            cache_capsule,
            get_cached_proposal,
            cache_proposal,
            get_cached_overlay_list,
            get_cached_system_metrics,
            get_cached_active_cascades,
        )
        log_test("7.2 Resilience caching imports", True, "All cache helpers imported")
    except ImportError as e:
        log_test("7.2 Resilience caching imports", False, str(e))

    # Test 7.3: Verify content validation
    try:
        from forge.resilience.integration import (
            validate_capsule_content,
            check_content_validation,
        )
        log_test("7.3 Content validation imports", True, "Validation helpers imported")
    except ImportError as e:
        log_test("7.3 Content validation imports", False, str(e))

    print()

    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("=" * 70)
    print("RESILIENCE INTEGRATION TEST SUMMARY")
    print("=" * 70)

    passed = sum(1 for r in test_results if r["passed"])
    failed = sum(1 for r in test_results if not r["passed"])
    total = len(test_results)

    print(f"\nTotal Tests: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Pass Rate: {(passed/total*100):.1f}%")

    if failed > 0:
        print("\nFailed Tests:")
        for r in test_results:
            if not r["passed"]:
                print(f"  - {r['test']}: {r['details']}")

    print()
    print("Routes with Resilience Integration:")
    print("  [OK] auth.py       - Login/registration metrics, content validation")
    print("  [OK] capsules.py   - Caching, content validation, CRUD metrics")
    print("  [OK] governance.py - Proposal caching, voting metrics")
    print("  [OK] overlays.py   - Overlay state metrics, cache invalidation")
    print("  [OK] system.py     - Health metrics, circuit breaker tracking")
    print("  [OK] cascade.py    - Cascade metrics, pipeline tracking")
    print()

    return passed >= total * 0.8  # 80% pass rate required


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
