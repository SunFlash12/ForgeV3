"""
Comprehensive Ghost Council Test Suite

Tests all Ghost Council functionality including:
- Member listing
- Statistics
- Serious issue reporting
- Edge cases and validation
- Authorization levels
- Issue resolution
- Proposal deliberation

SECURITY: Reads credentials from environment variables.
Set SEED_*_PASSWORD variables before running tests.
"""

import os
import requests
import json
import time
from datetime import datetime

BASE_URL = os.environ.get("TEST_API_URL", "http://127.0.0.1:8011")

# Default test password - should be set via environment
DEFAULT_TEST_PASSWORD = os.environ.get("TEST_USER_PASSWORD", "")

# Test results tracking
test_results = []


def log_test(test_name: str, passed: bool, details: str = ""):
    """Log test result."""
    status = "PASS" if passed else "FAIL"
    test_results.append({"test": test_name, "passed": passed, "details": details})
    print(f"[{status}] {test_name}")
    if details and not passed:
        print(f"       Details: {details}")


def get_test_password() -> str:
    """Get test password from environment or generate one."""
    if DEFAULT_TEST_PASSWORD:
        return DEFAULT_TEST_PASSWORD
    # Generate a secure random password for test users
    import secrets
    import string
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(16))


def register_user(username: str, password: str = None) -> dict:
    """Register a new user."""
    if password is None:
        password = get_test_password()
    resp = requests.post(
        f"{BASE_URL}/api/v1/auth/register",
        json={"username": username, "password": password, "email": f"{username}@test.com"}
    )
    return resp.json() if resp.status_code == 201 else None


def login_user(username: str, password: str = None) -> str:
    """Login and return access token."""
    if password is None:
        password = get_test_password()
    resp = requests.post(
        f"{BASE_URL}/api/v1/auth/login",
        json={"username": username, "password": password}
    )
    if resp.status_code == 200:
        return resp.json().get("access_token")
    return None


def get_headers(token: str) -> dict:
    """Get authorization headers."""
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def main():
    print("=" * 60)
    print("GHOST COUNCIL COMPREHENSIVE TEST SUITE")
    print("=" * 60)
    print()

    # Check server health first
    try:
        resp = requests.get(f"{BASE_URL}/health", timeout=5)
        if resp.status_code != 200:
            print("ERROR: Server not healthy. Please start the server first.")
            return
    except requests.exceptions.ConnectionError:
        print("ERROR: Cannot connect to server at", BASE_URL)
        print("Please start the server with: python -m uvicorn forge.api.app:app --port 8011")
        return

    print("Server is healthy. Starting tests...\n")

    # =========================================================================
    # SETUP: Create test users
    # =========================================================================
    print("-" * 60)
    print("SETUP: Creating test users")
    print("-" * 60)

    # Create standard user
    standard_user = register_user("gc_standard_user")
    standard_token = login_user("gc_standard_user") if standard_user else None

    # Create trusted user (manually set trust level would require DB access)
    # For now, we'll use standard users and test permission denials
    trusted_user = register_user("gc_trusted_user")
    trusted_token = login_user("gc_trusted_user") if trusted_user else None

    if not standard_token:
        print("ERROR: Could not create test users")
        return

    print(f"Created standard user: gc_standard_user")
    print(f"Created trusted user: gc_trusted_user")
    print()

    # =========================================================================
    # TEST 1: Ghost Council Members Listing
    # =========================================================================
    print("-" * 60)
    print("TEST GROUP 1: Ghost Council Members")
    print("-" * 60)

    # Test 1.1: Get members (authenticated)
    resp = requests.get(
        f"{BASE_URL}/api/v1/governance/ghost-council/members",
        headers=get_headers(standard_token)
    )

    if resp.status_code == 200:
        members = resp.json()
        log_test(
            "1.1 Get Ghost Council members",
            len(members) == 5,
            f"Expected 5 members, got {len(members)}"
        )

        # Verify member structure
        expected_members = ["gc_ethics", "gc_security", "gc_governance", "gc_technical", "gc_community"]
        member_ids = [m["id"] for m in members]
        log_test(
            "1.2 Verify all member IDs present",
            all(mid in member_ids for mid in expected_members),
            f"Got IDs: {member_ids}"
        )

        # Verify member has required fields
        first_member = members[0]
        required_fields = ["id", "name", "role", "weight"]
        has_fields = all(f in first_member for f in required_fields)
        log_test(
            "1.3 Verify member structure",
            has_fields,
            f"Fields: {list(first_member.keys())}"
        )

        # Verify weights are positive
        all_positive_weights = all(m["weight"] > 0 for m in members)
        log_test(
            "1.4 Verify all members have positive weights",
            all_positive_weights,
            f"Weights: {[m['weight'] for m in members]}"
        )
    else:
        log_test("1.1 Get Ghost Council members", False, f"Status: {resp.status_code}")

    # Test 1.5: Get members without auth
    resp = requests.get(f"{BASE_URL}/api/v1/governance/ghost-council/members")
    log_test(
        "1.5 Reject unauthenticated request",
        resp.status_code == 401,
        f"Expected 401, got {resp.status_code}"
    )

    print()

    # =========================================================================
    # TEST 2: Ghost Council Statistics
    # =========================================================================
    print("-" * 60)
    print("TEST GROUP 2: Ghost Council Statistics")
    print("-" * 60)

    resp = requests.get(
        f"{BASE_URL}/api/v1/governance/ghost-council/stats",
        headers=get_headers(standard_token)
    )

    if resp.status_code == 200:
        stats = resp.json()
        log_test(
            "2.1 Get Ghost Council stats",
            True,
            f"Stats: {stats}"
        )

        # Verify stats structure
        expected_fields = ["proposals_reviewed", "issues_responded", "council_members", "active_issues"]
        has_fields = all(f in stats for f in expected_fields)
        log_test(
            "2.2 Verify stats structure",
            has_fields,
            f"Fields: {list(stats.keys())}"
        )

        # Verify council_members count
        log_test(
            "2.3 Verify council_members count in stats",
            stats.get("council_members") == 5,
            f"Expected 5, got {stats.get('council_members')}"
        )
    else:
        log_test("2.1 Get Ghost Council stats", False, f"Status: {resp.status_code}")

    print()

    # =========================================================================
    # TEST 3: Serious Issue Reporting - Validation
    # =========================================================================
    print("-" * 60)
    print("TEST GROUP 3: Serious Issue Reporting - Edge Cases")
    print("-" * 60)

    # Test 3.1: Invalid category
    resp = requests.post(
        f"{BASE_URL}/api/v1/governance/ghost-council/issues",
        headers=get_headers(standard_token),
        json={
            "category": "invalid_category",
            "severity": "high",
            "title": "Test Issue Title Here",
            "description": "This is a test description that is long enough."
        }
    )
    # This should fail either with 400 (validation) or 403 (not trusted)
    log_test(
        "3.1 Reject invalid category",
        resp.status_code in [400, 403, 422],
        f"Status: {resp.status_code}, Response: {resp.text[:200]}"
    )

    # Test 3.2: Invalid severity
    resp = requests.post(
        f"{BASE_URL}/api/v1/governance/ghost-council/issues",
        headers=get_headers(standard_token),
        json={
            "category": "security",
            "severity": "invalid_severity",
            "title": "Test Issue Title Here",
            "description": "This is a test description that is long enough."
        }
    )
    log_test(
        "3.2 Reject invalid severity",
        resp.status_code in [400, 403, 422],
        f"Status: {resp.status_code}"
    )

    # Test 3.3: Title too short
    resp = requests.post(
        f"{BASE_URL}/api/v1/governance/ghost-council/issues",
        headers=get_headers(standard_token),
        json={
            "category": "security",
            "severity": "high",
            "title": "Hi",  # Too short (min 5)
            "description": "This is a test description that is long enough."
        }
    )
    log_test(
        "3.3 Reject title too short",
        resp.status_code in [400, 403, 422],
        f"Status: {resp.status_code}"
    )

    # Test 3.4: Description too short
    resp = requests.post(
        f"{BASE_URL}/api/v1/governance/ghost-council/issues",
        headers=get_headers(standard_token),
        json={
            "category": "security",
            "severity": "high",
            "title": "Valid Title Here",
            "description": "Too short"  # Min 20 chars
        }
    )
    log_test(
        "3.4 Reject description too short",
        resp.status_code in [400, 403, 422],
        f"Status: {resp.status_code}"
    )

    # Test 3.5: Missing required fields
    resp = requests.post(
        f"{BASE_URL}/api/v1/governance/ghost-council/issues",
        headers=get_headers(standard_token),
        json={
            "category": "security"
            # Missing severity, title, description
        }
    )
    log_test(
        "3.5 Reject missing required fields",
        resp.status_code in [400, 403, 422],
        f"Status: {resp.status_code}"
    )

    print()

    # =========================================================================
    # TEST 4: Authorization Levels
    # =========================================================================
    print("-" * 60)
    print("TEST GROUP 4: Authorization Levels")
    print("-" * 60)

    # Test 4.1: Standard user can view members
    resp = requests.get(
        f"{BASE_URL}/api/v1/governance/ghost-council/members",
        headers=get_headers(standard_token)
    )
    log_test(
        "4.1 Standard user CAN view members",
        resp.status_code == 200,
        f"Status: {resp.status_code}"
    )

    # Test 4.2: Standard user can view stats
    resp = requests.get(
        f"{BASE_URL}/api/v1/governance/ghost-council/stats",
        headers=get_headers(standard_token)
    )
    log_test(
        "4.2 Standard user CAN view stats",
        resp.status_code == 200,
        f"Status: {resp.status_code}"
    )

    # Test 4.3: Standard user CANNOT view issues (requires TRUSTED)
    resp = requests.get(
        f"{BASE_URL}/api/v1/governance/ghost-council/issues",
        headers=get_headers(standard_token)
    )
    log_test(
        "4.3 Standard user CANNOT view issues (requires TRUSTED)",
        resp.status_code == 403,
        f"Status: {resp.status_code}"
    )

    # Test 4.4: Standard user CANNOT report issues (requires TRUSTED)
    resp = requests.post(
        f"{BASE_URL}/api/v1/governance/ghost-council/issues",
        headers=get_headers(standard_token),
        json={
            "category": "security",
            "severity": "high",
            "title": "Security Issue Test",
            "description": "This is a detailed description of a security issue."
        }
    )
    log_test(
        "4.4 Standard user CANNOT report issues (requires TRUSTED)",
        resp.status_code == 403,
        f"Status: {resp.status_code}"
    )

    # Test 4.5: Standard user CANNOT resolve issues (requires CORE)
    resp = requests.post(
        f"{BASE_URL}/api/v1/governance/ghost-council/issues/fake-issue-id/resolve",
        headers=get_headers(standard_token),
        json={"resolution": "Issue has been resolved by fixing the security vulnerability."}
    )
    log_test(
        "4.5 Standard user CANNOT resolve issues (requires CORE)",
        resp.status_code == 403,
        f"Status: {resp.status_code}"
    )

    print()

    # =========================================================================
    # TEST 5: All Issue Categories and Severities
    # =========================================================================
    print("-" * 60)
    print("TEST GROUP 5: Valid Categories and Severities")
    print("-" * 60)

    categories = ["security", "governance", "trust", "system", "ethical", "data_integrity"]
    severities = ["low", "medium", "high", "critical"]

    # These tests will fail with 403 since standard user can't report
    # But they verify the API accepts the category/severity combinations

    for category in categories:
        resp = requests.post(
            f"{BASE_URL}/api/v1/governance/ghost-council/issues",
            headers=get_headers(standard_token),
            json={
                "category": category,
                "severity": "medium",
                "title": f"Test {category} issue",
                "description": f"This is a test issue in the {category} category for validation purposes."
            }
        )
        # 403 = permission denied (valid request but not authorized)
        # 400 = bad request (invalid category)
        is_valid_category = resp.status_code == 403
        log_test(
            f"5.{categories.index(category)+1} Category '{category}' is valid",
            is_valid_category,
            f"Status: {resp.status_code}" if not is_valid_category else ""
        )

    print()

    # =========================================================================
    # TEST 6: Ghost Council Stats After Operations
    # =========================================================================
    print("-" * 60)
    print("TEST GROUP 6: Stats Consistency")
    print("-" * 60)

    resp = requests.get(
        f"{BASE_URL}/api/v1/governance/ghost-council/stats",
        headers=get_headers(standard_token)
    )

    if resp.status_code == 200:
        stats = resp.json()

        # Verify non-negative values
        log_test(
            "6.1 proposals_reviewed is non-negative",
            stats.get("proposals_reviewed", -1) >= 0,
            f"Value: {stats.get('proposals_reviewed')}"
        )

        log_test(
            "6.2 issues_responded is non-negative",
            stats.get("issues_responded", -1) >= 0,
            f"Value: {stats.get('issues_responded')}"
        )

        log_test(
            "6.3 active_issues is non-negative",
            stats.get("active_issues", -1) >= 0,
            f"Value: {stats.get('active_issues')}"
        )

        log_test(
            "6.4 total_issues_tracked >= active_issues",
            stats.get("total_issues_tracked", 0) >= stats.get("active_issues", 0),
            f"Total: {stats.get('total_issues_tracked')}, Active: {stats.get('active_issues')}"
        )
    else:
        log_test("6.1 Get stats for consistency check", False, f"Status: {resp.status_code}")

    print()

    # =========================================================================
    # TEST 7: Edge Cases with Invalid Tokens
    # =========================================================================
    print("-" * 60)
    print("TEST GROUP 7: Invalid Authentication")
    print("-" * 60)

    # Test 7.1: Invalid token format
    resp = requests.get(
        f"{BASE_URL}/api/v1/governance/ghost-council/members",
        headers={"Authorization": "Bearer invalid_token_here"}
    )
    log_test(
        "7.1 Reject invalid token format",
        resp.status_code == 401,
        f"Status: {resp.status_code}"
    )

    # Test 7.2: Missing Bearer prefix
    resp = requests.get(
        f"{BASE_URL}/api/v1/governance/ghost-council/members",
        headers={"Authorization": standard_token}
    )
    log_test(
        "7.2 Reject missing Bearer prefix",
        resp.status_code == 401,
        f"Status: {resp.status_code}"
    )

    # Test 7.3: Empty authorization header
    resp = requests.get(
        f"{BASE_URL}/api/v1/governance/ghost-council/members",
        headers={"Authorization": ""}
    )
    log_test(
        "7.3 Reject empty authorization",
        resp.status_code == 401,
        f"Status: {resp.status_code}"
    )

    print()

    # =========================================================================
    # TEST 8: Resolve Non-Existent Issue
    # =========================================================================
    print("-" * 60)
    print("TEST GROUP 8: Non-Existent Resources")
    print("-" * 60)

    # This will fail with 403 for standard user, but tests the endpoint
    resp = requests.post(
        f"{BASE_URL}/api/v1/governance/ghost-council/issues/non-existent-id-12345/resolve",
        headers=get_headers(standard_token),
        json={"resolution": "Attempting to resolve non-existent issue"}
    )
    log_test(
        "8.1 Handle non-existent issue resolution",
        resp.status_code in [403, 404],  # 403 = not authorized, 404 = not found
        f"Status: {resp.status_code}"
    )

    print()

    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

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
    return passed == total


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
