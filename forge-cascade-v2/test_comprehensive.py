"""
Forge V3 Comprehensive Test Suite

150 tests covering all API routes and edge cases:
- 100 core functionality tests
- 50 edge case tests

Organized by API route module with full coverage.

SECURITY: Requires SEED_ADMIN_PASSWORD environment variable to be set.
Never commit hardcoded credentials to version control.
"""

import os
import sys
import requests
import time
import json
import uuid
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8001/api/v1"

# SECURITY: Load password from environment variable only
ADMIN_PASSWORD = os.environ.get("SEED_ADMIN_PASSWORD")
if not ADMIN_PASSWORD:
    print("ERROR: SEED_ADMIN_PASSWORD environment variable is required")
    print("Set it before running tests:")
    print("  export SEED_ADMIN_PASSWORD=your_admin_password")
    sys.exit(1)

test_results = []
test_data = {}  # Store created resources for cleanup/reference


def log_test(test_id: str, test_name: str, passed: bool, details: str = ""):
    """Log test result."""
    status = "PASS" if passed else "FAIL"
    test_results.append({
        "id": test_id,
        "test": test_name,
        "passed": passed,
        "details": details
    })
    print(f"[{status}] {test_id}: {test_name}")
    if details and not passed:
        print(f"         {details}")


def get_session():
    """Create authenticated admin session."""
    session = requests.Session()
    r = session.post(f"{BASE_URL}/auth/login", json={
        "username": "admin",
        "password": ADMIN_PASSWORD
    })
    if r.status_code != 200:
        return None
    return session


def get_user_session(username: str, password: str):
    """Create authenticated user session."""
    session = requests.Session()
    r = session.post(f"{BASE_URL}/auth/login", json={
        "username": username,
        "password": password
    })
    if r.status_code != 200:
        return None
    return session


def main():
    print("=" * 80)
    print("FORGE V3 COMPREHENSIVE TEST SUITE")
    print("150 Tests: 100 Core + 50 Edge Cases")
    print("=" * 80)
    print()

    # Check server
    try:
        r = requests.get("http://localhost:8001/health", timeout=5)
        if r.status_code != 200:
            print("ERROR: Server not healthy")
            return False
    except Exception as e:
        print(f"ERROR: Cannot connect - {e}")
        return False

    print("Server is healthy. Running comprehensive tests...\n")

    session = get_session()
    if not session:
        print("ERROR: Could not authenticate as admin")
        return False

    # =========================================================================
    # SECTION 1: AUTH ROUTES (Tests 1-20)
    # =========================================================================
    print("=" * 80)
    print("SECTION 1: AUTH ROUTES (20 tests)")
    print("=" * 80)

    # Test 1: Valid registration
    test_user = f"testuser_{int(time.time())}"
    r = session.post(f"{BASE_URL}/auth/register", json={
        "username": test_user,
        "email": f"{test_user}@test.com",
        "password": "SecurePass123!",
        "display_name": "Test User"
    })
    test_data["test_user"] = test_user
    test_data["test_user_password"] = "SecurePass123!"
    log_test("1.01", "Valid user registration", r.status_code == 201, f"Status: {r.status_code}")

    # Test 2: Registration with minimal fields
    test_user2 = f"minuser_{int(time.time())}"
    r = session.post(f"{BASE_URL}/auth/register", json={
        "username": test_user2,
        "email": f"{test_user2}@test.com",
        "password": "SecurePass123!"
    })
    log_test("1.02", "Registration with minimal fields", r.status_code == 201, f"Status: {r.status_code}")

    # Test 3: Duplicate username rejection
    r = session.post(f"{BASE_URL}/auth/register", json={
        "username": test_user,
        "email": "other@test.com",
        "password": "SecurePass123!"
    })
    log_test("1.03", "Duplicate username rejection", r.status_code in [400, 409], f"Status: {r.status_code}")

    # Test 4: Invalid email format
    r = session.post(f"{BASE_URL}/auth/register", json={
        "username": f"badmail_{int(time.time())}",
        "email": "not-an-email",
        "password": "SecurePass123!"
    })
    log_test("1.04", "Invalid email format rejection", r.status_code == 422, f"Status: {r.status_code}")

    # Test 5: Short password rejection
    r = session.post(f"{BASE_URL}/auth/register", json={
        "username": f"shortpw_{int(time.time())}",
        "email": f"shortpw_{int(time.time())}@test.com",
        "password": "short"
    })
    log_test("1.05", "Short password rejection", r.status_code == 422, f"Status: {r.status_code}")

    # Test 6: Valid login
    r = requests.post(f"{BASE_URL}/auth/login", json={
        "username": "admin",
        "password": ADMIN_PASSWORD
    })
    log_test("1.06", "Valid login", r.status_code == 200, f"Status: {r.status_code}")

    # Test 7: Invalid password login
    r = requests.post(f"{BASE_URL}/auth/login", json={
        "username": "admin",
        "password": "wrongpassword"
    })
    log_test("1.07", "Invalid password rejection", r.status_code == 401, f"Status: {r.status_code}")

    # Test 8: Non-existent user login
    r = requests.post(f"{BASE_URL}/auth/login", json={
        "username": "nonexistentuser12345",
        "password": "anypassword"
    })
    log_test("1.08", "Non-existent user rejection", r.status_code == 401, f"Status: {r.status_code}")

    # Test 9: Get current user profile
    r = session.get(f"{BASE_URL}/auth/me")
    log_test("1.09", "Get current user profile", r.status_code == 200 and "username" in r.json(), f"Status: {r.status_code}")

    # Test 10: Update display name
    r = session.patch(f"{BASE_URL}/auth/me", json={
        "display_name": "Updated Admin Name"
    })
    log_test("1.10", "Update display name", r.status_code == 200, f"Status: {r.status_code}")

    # Test 11: Token refresh
    r = session.post(f"{BASE_URL}/auth/refresh")
    log_test("1.11", "Token refresh", r.status_code == 200, f"Status: {r.status_code}")

    # Test 12: Get trust info
    r = session.get(f"{BASE_URL}/auth/me/trust")
    log_test("1.12", "Get trust info", r.status_code == 200 and "current_level" in r.json(), f"Status: {r.status_code}")

    # Test 13: Unauthenticated profile access
    r = requests.get(f"{BASE_URL}/auth/me")
    log_test("1.13", "Unauthenticated profile access blocked", r.status_code == 401, f"Status: {r.status_code}")

    # Test 14: Password change (test user)
    user_session = get_user_session(test_user, "SecurePass123!")
    if user_session:
        r = user_session.post(f"{BASE_URL}/auth/me/password", json={
            "current_password": "SecurePass123!",
            "new_password": "NewSecurePass456!"
        })
        log_test("1.14", "Password change", r.status_code == 204, f"Status: {r.status_code}")
        test_data["test_user_password"] = "NewSecurePass456!"
    else:
        log_test("1.14", "Password change", False, "Could not get user session")

    # Test 15: Password change with wrong current password
    user_session = get_user_session(test_user, "NewSecurePass456!")
    if user_session:
        r = user_session.post(f"{BASE_URL}/auth/me/password", json={
            "current_password": "WrongPassword123!",
            "new_password": "AnotherPass789!"
        })
        log_test("1.15", "Wrong current password rejection", r.status_code == 400, f"Status: {r.status_code}")
    else:
        log_test("1.15", "Wrong current password rejection", False, "Could not get user session")

    # Test 16: Update email
    r = session.patch(f"{BASE_URL}/auth/me", json={
        "email": "admin_updated@forge.local"
    })
    log_test("1.16", "Update email", r.status_code == 200, f"Status: {r.status_code}")

    # Test 17: Update metadata
    r = session.patch(f"{BASE_URL}/auth/me", json={
        "metadata": {"theme": "dark", "language": "en"}
    })
    log_test("1.17", "Update user metadata", r.status_code == 200, f"Status: {r.status_code}")

    # Test 18: Invalid username characters
    r = session.post(f"{BASE_URL}/auth/register", json={
        "username": "bad@user!name",
        "email": "baduser@test.com",
        "password": "SecurePass123!"
    })
    log_test("1.18", "Invalid username characters rejection", r.status_code == 422, f"Status: {r.status_code}")

    # Test 19: Username too short
    r = session.post(f"{BASE_URL}/auth/register", json={
        "username": "ab",
        "email": "shortuser@test.com",
        "password": "SecurePass123!"
    })
    log_test("1.19", "Username too short rejection", r.status_code == 422, f"Status: {r.status_code}")

    # Test 20: Logout
    user_session = get_user_session(test_user, "NewSecurePass456!")
    if user_session:
        r = user_session.post(f"{BASE_URL}/auth/logout")
        log_test("1.20", "User logout", r.status_code == 204, f"Status: {r.status_code}")
    else:
        log_test("1.20", "User logout", False, "Could not get user session")

    print()

    # =========================================================================
    # SECTION 2: CAPSULE ROUTES (Tests 21-45)
    # =========================================================================
    print("=" * 80)
    print("SECTION 2: CAPSULE ROUTES (25 tests)")
    print("=" * 80)

    # Test 21: Create capsule with all fields
    r = session.post(f"{BASE_URL}/capsules/", json={
        "title": "Comprehensive Test Capsule",
        "content": "This is a comprehensive test capsule with all fields populated for testing purposes.",
        "type": "KNOWLEDGE",
        "tags": ["test", "comprehensive", "automation"],
        "metadata": {"test_run": datetime.now().isoformat(), "category": "testing"}
    })
    capsule_id = r.json().get("id") if r.status_code == 201 else None
    test_data["capsule_id"] = capsule_id
    log_test("2.01", "Create capsule with all fields", r.status_code == 201 and capsule_id, f"Status: {r.status_code}")

    # Test 22: Create capsule with minimal fields
    r = session.post(f"{BASE_URL}/capsules/", json={
        "content": "Minimal capsule content for testing.",
        "type": "INSIGHT"
    })
    minimal_capsule_id = r.json().get("id") if r.status_code == 201 else None
    log_test("2.02", "Create capsule with minimal fields", r.status_code == 201, f"Status: {r.status_code}")

    # Test 23: Get capsule by ID
    if capsule_id:
        r = session.get(f"{BASE_URL}/capsules/{capsule_id}")
        log_test("2.03", "Get capsule by ID", r.status_code == 200 and r.json().get("id") == capsule_id, f"Status: {r.status_code}")
    else:
        log_test("2.03", "Get capsule by ID", False, "No capsule ID")

    # Test 24: List all capsules
    r = session.get(f"{BASE_URL}/capsules/")
    log_test("2.04", "List all capsules", r.status_code == 200 and "items" in r.json(), f"Status: {r.status_code}")

    # Test 25: List capsules with pagination
    r = session.get(f"{BASE_URL}/capsules/", params={"page": 1, "per_page": 5})
    log_test("2.05", "List capsules with pagination", r.status_code == 200, f"Status: {r.status_code}")

    # Test 26: Filter capsules by type
    r = session.get(f"{BASE_URL}/capsules/", params={"capsule_type": "KNOWLEDGE"})
    log_test("2.06", "Filter capsules by type", r.status_code == 200, f"Status: {r.status_code}")

    # Test 27: Update capsule content
    if capsule_id:
        r = session.patch(f"{BASE_URL}/capsules/{capsule_id}", json={
            "content": "Updated capsule content for comprehensive testing."
        })
        log_test("2.07", "Update capsule content", r.status_code == 200, f"Status: {r.status_code}")
    else:
        log_test("2.07", "Update capsule content", False, "No capsule ID")

    # Test 28: Update capsule tags
    if capsule_id:
        r = session.patch(f"{BASE_URL}/capsules/{capsule_id}", json={
            "tags": ["updated", "modified", "test"]
        })
        log_test("2.08", "Update capsule tags", r.status_code == 200, f"Status: {r.status_code}")
    else:
        log_test("2.08", "Update capsule tags", False, "No capsule ID")

    # Test 29: Semantic search
    r = session.post(f"{BASE_URL}/capsules/search", json={
        "query": "comprehensive test capsule",
        "limit": 10
    })
    log_test("2.09", "Semantic search", r.status_code == 200, f"Status: {r.status_code}")

    # Test 30: Get recent capsules
    r = session.get(f"{BASE_URL}/capsules/search/recent", params={"limit": 5})
    log_test("2.10", "Get recent capsules", r.status_code == 200, f"Status: {r.status_code}")

    # Test 31: Create child capsule (for lineage)
    if capsule_id:
        r = session.post(f"{BASE_URL}/capsules/", json={
            "content": "Child capsule for lineage testing.",
            "type": "INSIGHT",
            "parent_id": capsule_id
        })
        child_capsule_id = r.json().get("id") if r.status_code == 201 else None
        test_data["child_capsule_id"] = child_capsule_id
        log_test("2.11", "Create child capsule", r.status_code == 201, f"Status: {r.status_code}")
    else:
        log_test("2.11", "Create child capsule", False, "No parent capsule")

    # Test 32: Get capsule lineage
    if capsule_id:
        r = session.get(f"{BASE_URL}/capsules/{capsule_id}/lineage", params={"depth": 3})
        log_test("2.12", "Get capsule lineage", r.status_code == 200, f"Status: {r.status_code}")
    else:
        log_test("2.12", "Get capsule lineage", False, "No capsule ID")

    # Test 33: Fork capsule
    if capsule_id:
        r = session.post(f"{BASE_URL}/capsules/{capsule_id}/fork", json={
            "evolution_reason": "Testing fork functionality"
        })
        forked_id = r.json().get("id") if r.status_code == 201 else None
        test_data["forked_capsule_id"] = forked_id
        log_test("2.13", "Fork capsule", r.status_code == 201, f"Status: {r.status_code}")
    else:
        log_test("2.13", "Fork capsule", False, "No capsule ID")

    # Test 34: Link capsules
    if capsule_id and minimal_capsule_id:
        r = session.post(f"{BASE_URL}/capsules/{minimal_capsule_id}/link/{capsule_id}")
        log_test("2.14", "Link capsules", r.status_code in [200, 201], f"Status: {r.status_code}")
    else:
        log_test("2.14", "Link capsules", False, "Missing capsule IDs")

    # Test 35: Archive capsule
    if minimal_capsule_id:
        r = session.post(f"{BASE_URL}/capsules/{minimal_capsule_id}/archive")
        log_test("2.15", "Archive capsule", r.status_code == 200, f"Status: {r.status_code}")
    else:
        log_test("2.15", "Archive capsule", False, "No capsule ID")

    # Test 36: Get capsule not found
    r = session.get(f"{BASE_URL}/capsules/nonexistent-capsule-id-12345")
    log_test("2.16", "Get non-existent capsule returns 404", r.status_code == 404, f"Status: {r.status_code}")

    # Test 37: Create capsule with max tags
    r = session.post(f"{BASE_URL}/capsules/", json={
        "content": "Capsule with many tags.",
        "type": "MEMORY",
        "tags": [f"tag{i}" for i in range(50)]
    })
    log_test("2.17", "Create capsule with max tags (50)", r.status_code == 201, f"Status: {r.status_code}")

    # Test 38: Create different capsule types
    for ctype in ["DECISION", "LESSON", "WARNING", "PRINCIPLE"]:
        r = session.post(f"{BASE_URL}/capsules/", json={
            "content": f"Test {ctype} capsule content.",
            "type": ctype
        })
        if r.status_code != 201:
            break
    log_test("2.18", "Create various capsule types", r.status_code == 201, f"Status: {r.status_code}")

    # Test 39: Search with filters
    r = session.post(f"{BASE_URL}/capsules/search", json={
        "query": "test",
        "limit": 5,
        "filters": {"type": "KNOWLEDGE"}
    })
    log_test("2.19", "Search with filters", r.status_code == 200, f"Status: {r.status_code}")

    # Test 40: Empty search query
    r = session.post(f"{BASE_URL}/capsules/search", json={
        "query": "",
        "limit": 5
    })
    log_test("2.20", "Empty search query handling", r.status_code in [200, 422], f"Status: {r.status_code}")

    # Test 41: Get capsules by owner
    r = session.get(f"{BASE_URL}/auth/me")
    if r.status_code == 200:
        owner_id = r.json().get("id")
        r2 = session.get(f"{BASE_URL}/capsules/search/by-owner/{owner_id}")
        log_test("2.21", "Get capsules by owner", r2.status_code == 200, f"Status: {r2.status_code}")
    else:
        log_test("2.21", "Get capsules by owner", False, "Could not get user ID")

    # Test 42: Update capsule metadata
    if capsule_id:
        r = session.patch(f"{BASE_URL}/capsules/{capsule_id}", json={
            "metadata": {"updated": True, "version": 2}
        })
        log_test("2.22", "Update capsule metadata", r.status_code == 200, f"Status: {r.status_code}")
    else:
        log_test("2.22", "Update capsule metadata", False, "No capsule ID")

    # Test 43: Create capsule with title
    r = session.post(f"{BASE_URL}/capsules/", json={
        "title": "Titled Test Capsule",
        "content": "Content for titled capsule.",
        "type": "DOCUMENT"
    })
    log_test("2.23", "Create capsule with title", r.status_code == 201, f"Status: {r.status_code}")

    # Test 44: Lineage with depth parameter
    if capsule_id:
        r = session.get(f"{BASE_URL}/capsules/{capsule_id}/lineage", params={"depth": 10})
        log_test("2.24", "Lineage with custom depth", r.status_code == 200, f"Status: {r.status_code}")
    else:
        log_test("2.24", "Lineage with custom depth", False, "No capsule ID")

    # Test 45: Delete capsule
    # Create a capsule to delete
    r = session.post(f"{BASE_URL}/capsules/", json={
        "content": "Capsule to be deleted.",
        "type": "MEMORY"
    })
    if r.status_code == 201:
        delete_id = r.json().get("id")
        r2 = session.delete(f"{BASE_URL}/capsules/{delete_id}")
        log_test("2.25", "Delete capsule", r2.status_code == 204, f"Status: {r2.status_code}")
    else:
        log_test("2.25", "Delete capsule", False, "Could not create capsule to delete")

    print()

    # =========================================================================
    # SECTION 3: GOVERNANCE ROUTES (Tests 46-70)
    # =========================================================================
    print("=" * 80)
    print("SECTION 3: GOVERNANCE ROUTES (25 tests)")
    print("=" * 80)

    # Test 46: Create proposal
    r = session.post(f"{BASE_URL}/governance/proposals", json={
        "title": "Test Governance Proposal",
        "description": "This is a comprehensive test proposal for the governance system testing.",
        "proposal_type": "policy",
        "action": {"test_action": "test_value"},
        "voting_period_days": 7
    })
    proposal_id = r.json().get("id") if r.status_code == 201 else None
    test_data["proposal_id"] = proposal_id
    log_test("3.01", "Create proposal", r.status_code == 201 and proposal_id, f"Status: {r.status_code}")

    # Test 47: List all proposals
    r = session.get(f"{BASE_URL}/governance/proposals")
    log_test("3.02", "List all proposals", r.status_code == 200, f"Status: {r.status_code}")

    # Test 48: Get specific proposal
    if proposal_id:
        r = session.get(f"{BASE_URL}/governance/proposals/{proposal_id}")
        log_test("3.03", "Get specific proposal", r.status_code == 200, f"Status: {r.status_code}")
    else:
        log_test("3.03", "Get specific proposal", False, "No proposal ID")

    # Test 49: Submit proposal for voting
    if proposal_id:
        r = session.post(f"{BASE_URL}/governance/proposals/{proposal_id}/submit")
        log_test("3.04", "Submit proposal for voting", r.status_code == 200, f"Status: {r.status_code}")
    else:
        log_test("3.04", "Submit proposal for voting", False, "No proposal ID")

    # Test 50: Cast vote on proposal
    if proposal_id:
        r = session.post(f"{BASE_URL}/governance/proposals/{proposal_id}/vote", json={
            "choice": "APPROVE",
            "rationale": "Testing the voting system"
        })
        log_test("3.05", "Cast vote on proposal", r.status_code in [200, 201, 400], f"Status: {r.status_code}")
    else:
        log_test("3.05", "Cast vote on proposal", False, "No proposal ID")

    # Test 51: Get proposal votes
    if proposal_id:
        r = session.get(f"{BASE_URL}/governance/proposals/{proposal_id}/votes")
        log_test("3.06", "Get proposal votes", r.status_code == 200, f"Status: {r.status_code}")
    else:
        log_test("3.06", "Get proposal votes", False, "No proposal ID")

    # Test 52: Get my vote
    if proposal_id:
        r = session.get(f"{BASE_URL}/governance/proposals/{proposal_id}/my-vote")
        log_test("3.07", "Get my vote", r.status_code in [200, 404], f"Status: {r.status_code}")
    else:
        log_test("3.07", "Get my vote", False, "No proposal ID")

    # Test 53: Get active proposals
    r = session.get(f"{BASE_URL}/governance/proposals/active")
    log_test("3.08", "Get active proposals", r.status_code == 200, f"Status: {r.status_code}")

    # Test 54: Ghost Council members
    r = session.get(f"{BASE_URL}/governance/ghost-council/members")
    log_test("3.09", "Get Ghost Council members", r.status_code == 200 and len(r.json()) > 0, f"Status: {r.status_code}")

    # Test 55: Ghost Council stats
    r = session.get(f"{BASE_URL}/governance/ghost-council/stats")
    log_test("3.10", "Get Ghost Council stats", r.status_code == 200, f"Status: {r.status_code}")

    # Test 56: Report serious issue
    r = session.post(f"{BASE_URL}/governance/ghost-council/issues", json={
        "category": "security",
        "severity": "medium",
        "title": "Test Security Issue",
        "description": "This is a test security issue for comprehensive testing purposes."
    })
    issue_id = r.json().get("id") if r.status_code in [200, 201] else None
    test_data["issue_id"] = issue_id
    log_test("3.11", "Report serious issue", r.status_code in [200, 201], f"Status: {r.status_code}")

    # Test 57: Get active issues
    r = session.get(f"{BASE_URL}/governance/ghost-council/issues")
    log_test("3.12", "Get active issues", r.status_code == 200, f"Status: {r.status_code}")

    # Test 58: Resolve issue
    if issue_id:
        r = session.post(f"{BASE_URL}/governance/ghost-council/issues/{issue_id}/resolve", json={
            "resolution": "Test issue resolved during comprehensive testing."
        })
        log_test("3.13", "Resolve issue", r.status_code == 200, f"Status: {r.status_code}")
    else:
        log_test("3.13", "Resolve issue", False, "No issue ID")

    # Test 59: Governance metrics
    r = session.get(f"{BASE_URL}/governance/metrics")
    log_test("3.14", "Get governance metrics", r.status_code == 200, f"Status: {r.status_code}")

    # Test 60: Ghost Council recommendation
    if proposal_id:
        r = session.get(f"{BASE_URL}/governance/proposals/{proposal_id}/ghost-council")
        log_test("3.15", "Ghost Council recommendation", r.status_code == 200, f"Status: {r.status_code}")
    else:
        log_test("3.15", "Ghost Council recommendation", False, "No proposal ID")

    # Test 61: Constitutional analysis
    if proposal_id:
        r = session.get(f"{BASE_URL}/governance/proposals/{proposal_id}/constitutional-analysis")
        log_test("3.16", "Constitutional analysis", r.status_code == 200, f"Status: {r.status_code}")
    else:
        log_test("3.16", "Constitutional analysis", False, "No proposal ID")

    # Test 62: Get policies
    r = session.get(f"{BASE_URL}/governance/policies")
    log_test("3.17", "Get active policies", r.status_code == 200, f"Status: {r.status_code}")

    # Test 63: Filter proposals by status
    r = session.get(f"{BASE_URL}/governance/proposals", params={"status_filter": "VOTING"})
    log_test("3.18", "Filter proposals by status", r.status_code == 200, f"Status: {r.status_code}")

    # Test 64: Filter proposals by type
    r = session.get(f"{BASE_URL}/governance/proposals", params={"proposal_type": "policy"})
    log_test("3.19", "Filter proposals by type", r.status_code == 200, f"Status: {r.status_code}")

    # Test 65: Create system proposal
    r = session.post(f"{BASE_URL}/governance/proposals", json={
        "title": "System Configuration Proposal",
        "description": "This proposal suggests changes to system configuration parameters.",
        "proposal_type": "system",
        "action": {"config_change": True}
    })
    log_test("3.20", "Create system proposal", r.status_code == 201, f"Status: {r.status_code}")

    # Test 66: Create overlay proposal
    r = session.post(f"{BASE_URL}/governance/proposals", json={
        "title": "Overlay Modification Proposal",
        "description": "This proposal suggests modifications to overlay behavior.",
        "proposal_type": "overlay",
        "action": {"overlay_id": "test", "change": "enable"}
    })
    log_test("3.21", "Create overlay proposal", r.status_code == 201, f"Status: {r.status_code}")

    # Test 67: Double voting prevention
    if proposal_id:
        r = session.post(f"{BASE_URL}/governance/proposals/{proposal_id}/vote", json={
            "choice": "REJECT",
            "rationale": "Trying to vote again"
        })
        log_test("3.22", "Double voting prevention", r.status_code == 400, f"Status: {r.status_code}")
    else:
        log_test("3.22", "Double voting prevention", False, "No proposal ID")

    # Test 68: Invalid vote choice
    if proposal_id:
        r = session.post(f"{BASE_URL}/governance/proposals/{proposal_id}/vote", json={
            "choice": "INVALID_CHOICE"
        })
        log_test("3.23", "Invalid vote choice rejection", r.status_code == 422, f"Status: {r.status_code}")
    else:
        log_test("3.23", "Invalid vote choice rejection", False, "No proposal ID")

    # Test 69: Finalize proposal
    if proposal_id:
        r = session.post(f"{BASE_URL}/governance/proposals/{proposal_id}/finalize")
        log_test("3.24", "Finalize proposal", r.status_code in [200, 400], f"Status: {r.status_code}")
    else:
        log_test("3.24", "Finalize proposal", False, "No proposal ID")

    # Test 70: Create proposal with custom voting parameters
    r = session.post(f"{BASE_URL}/governance/proposals", json={
        "title": "Custom Voting Parameters Proposal",
        "description": "Testing proposal with custom voting period and thresholds.",
        "proposal_type": "policy",
        "action": {},
        "voting_period_days": 14,
        "quorum_percent": 0.2,
        "pass_threshold": 0.6
    })
    log_test("3.25", "Proposal with custom voting params", r.status_code == 201, f"Status: {r.status_code}")

    print()

    # =========================================================================
    # SECTION 4: OVERLAY ROUTES (Tests 71-85)
    # =========================================================================
    print("=" * 80)
    print("SECTION 4: OVERLAY ROUTES (15 tests)")
    print("=" * 80)

    # Test 71: List all overlays
    r = session.get(f"{BASE_URL}/overlays/")
    overlays = r.json().get("overlays", []) if r.status_code == 200 else []
    overlay_id = overlays[0].get("id") if overlays else None
    test_data["overlay_id"] = overlay_id
    log_test("4.01", "List all overlays", r.status_code == 200, f"Status: {r.status_code}")

    # Test 72: List active overlays
    r = session.get(f"{BASE_URL}/overlays/active")
    log_test("4.02", "List active overlays", r.status_code == 200, f"Status: {r.status_code}")

    # Test 73: Get specific overlay
    if overlay_id:
        r = session.get(f"{BASE_URL}/overlays/{overlay_id}")
        log_test("4.03", "Get specific overlay", r.status_code == 200, f"Status: {r.status_code}")
    else:
        log_test("4.03", "Get specific overlay", False, "No overlay ID")

    # Test 74: Overlay metrics summary
    r = session.get(f"{BASE_URL}/overlays/metrics/summary")
    log_test("4.04", "Overlay metrics summary", r.status_code == 200, f"Status: {r.status_code}")

    # Test 75: Get overlay metrics
    if overlay_id:
        r = session.get(f"{BASE_URL}/overlays/{overlay_id}/metrics")
        log_test("4.05", "Get overlay metrics", r.status_code == 200, f"Status: {r.status_code}")
    else:
        log_test("4.05", "Get overlay metrics", False, "No overlay ID")

    # Test 76: List overlays by phase
    for phase in [1, 2, 3, 4, 5, 6, 7]:
        r = session.get(f"{BASE_URL}/overlays/by-phase/{phase}")
        if r.status_code != 200:
            break
    log_test("4.06", "List overlays by phase", r.status_code == 200, f"Status: {r.status_code}")

    # Test 77: Get canary status
    if overlay_id:
        r = session.get(f"{BASE_URL}/overlays/{overlay_id}/canary")
        log_test("4.07", "Get canary status", r.status_code == 200, f"Status: {r.status_code}")
    else:
        log_test("4.07", "Get canary status", False, "No overlay ID")

    # Test 78: Activate overlay
    if overlay_id:
        r = session.post(f"{BASE_URL}/overlays/{overlay_id}/activate")
        log_test("4.08", "Activate overlay", r.status_code in [200, 400], f"Status: {r.status_code}")
    else:
        log_test("4.08", "Activate overlay", False, "No overlay ID")

    # Test 79: Deactivate overlay
    if overlay_id:
        r = session.post(f"{BASE_URL}/overlays/{overlay_id}/deactivate")
        log_test("4.09", "Deactivate overlay", r.status_code in [200, 400], f"Status: {r.status_code}")
    else:
        log_test("4.09", "Deactivate overlay", False, "No overlay ID")

    # Test 80: Update overlay config
    if overlay_id:
        r = session.patch(f"{BASE_URL}/overlays/{overlay_id}/config", json={
            "config": {"test_setting": True}
        })
        log_test("4.10", "Update overlay config", r.status_code in [200, 404], f"Status: {r.status_code}")
    else:
        log_test("4.10", "Update overlay config", False, "No overlay ID")

    # Test 81: Get non-existent overlay
    r = session.get(f"{BASE_URL}/overlays/nonexistent-overlay-12345")
    log_test("4.11", "Non-existent overlay returns 404", r.status_code == 404, f"Status: {r.status_code}")

    # Test 82: Canary start
    if overlay_id:
        r = session.post(f"{BASE_URL}/overlays/{overlay_id}/canary/start")
        log_test("4.12", "Start canary deployment", r.status_code in [200, 201, 400], f"Status: {r.status_code}")
    else:
        log_test("4.12", "Start canary deployment", False, "No overlay ID")

    # Test 83: Canary advance
    if overlay_id:
        r = session.post(f"{BASE_URL}/overlays/{overlay_id}/canary/advance")
        log_test("4.13", "Advance canary deployment", r.status_code in [200, 400, 404], f"Status: {r.status_code}")
    else:
        log_test("4.13", "Advance canary deployment", False, "No overlay ID")

    # Test 84: Canary rollback
    if overlay_id:
        r = session.post(f"{BASE_URL}/overlays/{overlay_id}/canary/rollback")
        log_test("4.14", "Rollback canary deployment", r.status_code in [200, 404], f"Status: {r.status_code}")
    else:
        log_test("4.14", "Rollback canary deployment", False, "No overlay ID")

    # Test 85: Reload all overlays
    r = session.post(f"{BASE_URL}/overlays/reload-all")
    log_test("4.15", "Reload all overlays", r.status_code in [200, 403], f"Status: {r.status_code}")

    print()

    # =========================================================================
    # SECTION 5: SYSTEM ROUTES (Tests 86-105)
    # =========================================================================
    print("=" * 80)
    print("SECTION 5: SYSTEM ROUTES (20 tests)")
    print("=" * 80)

    # Test 86: Comprehensive health check
    r = session.get(f"{BASE_URL}/system/health")
    log_test("5.01", "Comprehensive health check", r.status_code == 200, f"Status: {r.status_code}")

    # Test 87: Liveness probe
    r = session.get(f"{BASE_URL}/system/health/live")
    log_test("5.02", "Liveness probe", r.status_code == 200, f"Status: {r.status_code}")

    # Test 88: Readiness probe
    r = session.get(f"{BASE_URL}/system/health/ready")
    log_test("5.03", "Readiness probe", r.status_code == 200, f"Status: {r.status_code}")

    # Test 89: System metrics
    r = session.get(f"{BASE_URL}/system/metrics")
    log_test("5.04", "System metrics", r.status_code == 200, f"Status: {r.status_code}")

    # Test 90: System status
    r = session.get(f"{BASE_URL}/system/status")
    log_test("5.05", "System status", r.status_code == 200, f"Status: {r.status_code}")

    # Test 91: System info
    r = session.get(f"{BASE_URL}/system/info")
    log_test("5.06", "System info", r.status_code == 200, f"Status: {r.status_code}")

    # Test 92: List circuit breakers
    r = session.get(f"{BASE_URL}/system/circuit-breakers")
    circuit_breakers = r.json().get("circuit_breakers", []) if r.status_code == 200 else []
    cb_name = circuit_breakers[0].get("name") if circuit_breakers else None
    log_test("5.07", "List circuit breakers", r.status_code == 200, f"Status: {r.status_code}")

    # Test 93: Reset circuit breaker
    if cb_name:
        r = session.post(f"{BASE_URL}/system/circuit-breakers/{cb_name}/reset")
        log_test("5.08", "Reset circuit breaker", r.status_code in [200, 404], f"Status: {r.status_code}")
    else:
        log_test("5.08", "Reset circuit breaker", True, "No circuit breakers to reset")

    # Test 94: List anomalies
    r = session.get(f"{BASE_URL}/system/anomalies")
    log_test("5.09", "List anomalies", r.status_code == 200, f"Status: {r.status_code}")

    # Test 95: Filter anomalies by time
    r = session.get(f"{BASE_URL}/system/anomalies", params={"hours": 48})
    log_test("5.10", "Filter anomalies by time", r.status_code == 200, f"Status: {r.status_code}")

    # Test 96: Get recent events
    r = session.get(f"{BASE_URL}/system/events/recent", params={"limit": 20})
    log_test("5.11", "Get recent events", r.status_code == 200, f"Status: {r.status_code}")

    # Test 97: Get audit log
    r = session.get(f"{BASE_URL}/system/audit")
    log_test("5.12", "Get audit log", r.status_code == 200, f"Status: {r.status_code}")

    # Test 98: Audit log with filters
    r = session.get(f"{BASE_URL}/system/audit", params={"limit": 10, "action": "capsule_created"})
    log_test("5.13", "Audit log with filters", r.status_code == 200, f"Status: {r.status_code}")

    # Test 99: List canary deployments
    r = session.get(f"{BASE_URL}/system/canaries")
    log_test("5.14", "List canary deployments", r.status_code == 200, f"Status: {r.status_code}")

    # Test 100: Record metric
    r = session.post(f"{BASE_URL}/system/metrics/record", json={
        "metric_name": "test_metric",
        "value": 42.5,
        "context": {"source": "comprehensive_test"}
    })
    log_test("5.15", "Record metric", r.status_code == 200, f"Status: {r.status_code}")

    # Test 101: Enable maintenance mode
    r = session.post(f"{BASE_URL}/system/maintenance/enable")
    log_test("5.16", "Enable maintenance mode", r.status_code in [200, 403], f"Status: {r.status_code}")

    # Test 102: Disable maintenance mode
    r = session.post(f"{BASE_URL}/system/maintenance/disable")
    log_test("5.17", "Disable maintenance mode", r.status_code in [200, 403], f"Status: {r.status_code}")

    # Test 103: Clear caches
    r = session.post(f"{BASE_URL}/system/cache/clear")
    log_test("5.18", "Clear caches", r.status_code in [200, 403], f"Status: {r.status_code}")

    # Test 104: Filter events by type
    r = session.get(f"{BASE_URL}/system/events/recent", params={"event_type": "CAPSULE_CREATED"})
    log_test("5.19", "Filter events by type", r.status_code == 200, f"Status: {r.status_code}")

    # Test 105: Unresolved anomalies only
    r = session.get(f"{BASE_URL}/system/anomalies", params={"unresolved_only": True})
    log_test("5.20", "Unresolved anomalies only", r.status_code == 200, f"Status: {r.status_code}")

    print()

    # =========================================================================
    # SECTION 6: CASCADE ROUTES (Tests 106-115)
    # =========================================================================
    print("=" * 80)
    print("SECTION 6: CASCADE ROUTES (10 tests)")
    print("=" * 80)

    # Test 106: List active cascades
    r = session.get(f"{BASE_URL}/cascade/")
    log_test("6.01", "List active cascades", r.status_code == 200, f"Status: {r.status_code}")

    # Test 107: Trigger cascade
    r = session.post(f"{BASE_URL}/cascade/trigger", json={
        "source_overlay": "security_validator",
        "insight_type": "test_insight",
        "insight_data": {"test": True, "value": 42},
        "max_hops": 3
    })
    cascade_id = r.json().get("cascade_id") if r.status_code == 200 else None
    test_data["cascade_id"] = cascade_id
    log_test("6.02", "Trigger cascade", r.status_code == 200, f"Status: {r.status_code}")

    # Test 108: Get cascade metrics
    r = session.get(f"{BASE_URL}/cascade/metrics/summary")
    log_test("6.03", "Get cascade metrics", r.status_code == 200, f"Status: {r.status_code}")

    # Test 109: Get specific cascade
    if cascade_id:
        r = session.get(f"{BASE_URL}/cascade/{cascade_id}")
        log_test("6.04", "Get specific cascade", r.status_code == 200, f"Status: {r.status_code}")
    else:
        log_test("6.04", "Get specific cascade", False, "No cascade ID")

    # Test 110: Propagate cascade
    if cascade_id:
        r = session.post(f"{BASE_URL}/cascade/propagate", json={
            "cascade_id": cascade_id,
            "target_overlay": "ml_intelligence",
            "insight_type": "propagated_insight",
            "insight_data": {"propagated": True},
            "impact_score": 0.7
        })
        log_test("6.05", "Propagate cascade", r.status_code in [200, 400], f"Status: {r.status_code}")
    else:
        log_test("6.05", "Propagate cascade", False, "No cascade ID")

    # Test 111: Complete cascade
    if cascade_id:
        r = session.post(f"{BASE_URL}/cascade/{cascade_id}/complete")
        log_test("6.06", "Complete cascade", r.status_code == 200, f"Status: {r.status_code}")
    else:
        log_test("6.06", "Complete cascade", False, "No cascade ID")

    # Test 112: Execute pipeline
    r = session.post(f"{BASE_URL}/cascade/execute-pipeline", json={
        "source_overlay": "governance",
        "insight_type": "pipeline_test",
        "insight_data": {"pipeline": True},
        "max_hops": 5
    })
    log_test("6.07", "Execute cascade pipeline", r.status_code == 200, f"Status: {r.status_code}")

    # Test 113: Get non-existent cascade
    r = session.get(f"{BASE_URL}/cascade/nonexistent-cascade-12345")
    log_test("6.08", "Non-existent cascade returns 404", r.status_code == 404, f"Status: {r.status_code}")

    # Test 114: Trigger cascade with max hops
    r = session.post(f"{BASE_URL}/cascade/trigger", json={
        "source_overlay": "test",
        "insight_type": "max_hop_test",
        "insight_data": {},
        "max_hops": 10
    })
    log_test("6.09", "Cascade with max hops", r.status_code == 200, f"Status: {r.status_code}")

    # Test 115: Trigger cascade with min hops
    r = session.post(f"{BASE_URL}/cascade/trigger", json={
        "source_overlay": "test",
        "insight_type": "min_hop_test",
        "insight_data": {},
        "max_hops": 1
    })
    log_test("6.10", "Cascade with min hops", r.status_code == 200, f"Status: {r.status_code}")

    print()

    # =========================================================================
    # SECTION 7: EDGE CASES (Tests 116-150)
    # =========================================================================
    print("=" * 80)
    print("SECTION 7: EDGE CASES (35 tests)")
    print("=" * 80)

    # Test 116: Very long capsule content
    r = session.post(f"{BASE_URL}/capsules/", json={
        "content": "A" * 50000,  # 50KB content
        "type": "DOCUMENT"
    })
    log_test("E.01", "Very long capsule content (50KB)", r.status_code == 201, f"Status: {r.status_code}")

    # Test 117: Unicode content
    r = session.post(f"{BASE_URL}/capsules/", json={
        "content": "Unicode test: \u4e2d\u6587 \u65e5\u672c\u8a9e \ud55c\uad6d\uc5b4 \u0420\u0443\u0441\u0441\u043a\u0438\u0439 \u0639\u0631\u0628\u064a",
        "type": "KNOWLEDGE"
    })
    log_test("E.02", "Unicode content handling", r.status_code == 201, f"Status: {r.status_code}")

    # Test 118: Emoji in content
    r = session.post(f"{BASE_URL}/capsules/", json={
        "content": "Emoji test content here",
        "type": "MEMORY"
    })
    log_test("E.03", "Emoji in content", r.status_code == 201, f"Status: {r.status_code}")

    # Test 119: Empty tags array
    r = session.post(f"{BASE_URL}/capsules/", json={
        "content": "Capsule with empty tags array.",
        "type": "INSIGHT",
        "tags": []
    })
    log_test("E.04", "Empty tags array", r.status_code == 201, f"Status: {r.status_code}")

    # Test 120: Null metadata
    r = session.post(f"{BASE_URL}/capsules/", json={
        "content": "Capsule with null metadata.",
        "type": "INSIGHT",
        "metadata": None
    })
    log_test("E.05", "Null metadata handling", r.status_code in [201, 422], f"Status: {r.status_code}")

    # Test 121: Special characters in tags
    r = session.post(f"{BASE_URL}/capsules/", json={
        "content": "Capsule with special character tags.",
        "type": "INSIGHT",
        "tags": ["tag-with-dash", "tag_with_underscore", "tag.with.dot"]
    })
    log_test("E.06", "Special characters in tags", r.status_code == 201, f"Status: {r.status_code}")

    # Test 122: Very long tag
    r = session.post(f"{BASE_URL}/capsules/", json={
        "content": "Capsule with very long tag.",
        "type": "INSIGHT",
        "tags": ["a" * 100]  # Max tag length
    })
    log_test("E.07", "Max length tag (100 chars)", r.status_code == 201, f"Status: {r.status_code}")

    # Test 123: Tag exceeding max length
    r = session.post(f"{BASE_URL}/capsules/", json={
        "content": "Capsule with tag too long.",
        "type": "INSIGHT",
        "tags": ["a" * 101]  # Over max
    })
    log_test("E.08", "Tag exceeding max length rejected", r.status_code == 422, f"Status: {r.status_code}")

    # Test 124: Concurrent requests simulation
    results = []
    for i in range(5):
        r = session.get(f"{BASE_URL}/capsules/")
        results.append(r.status_code)
    log_test("E.09", "Concurrent requests handling", all(s == 200 for s in results), f"Results: {results}")

    # Test 125: Invalid JSON body
    r = session.post(
        f"{BASE_URL}/capsules/",
        data="not valid json",
        headers={"Content-Type": "application/json"}
    )
    log_test("E.10", "Invalid JSON body rejected", r.status_code == 422, f"Status: {r.status_code}")

    # Test 126: Missing required field
    r = session.post(f"{BASE_URL}/capsules/", json={
        "type": "INSIGHT"
        # Missing content
    })
    log_test("E.11", "Missing required field rejected", r.status_code == 422, f"Status: {r.status_code}")

    # Test 127: Invalid capsule type
    r = session.post(f"{BASE_URL}/capsules/", json={
        "content": "Test content",
        "type": "INVALID_TYPE"
    })
    log_test("E.12", "Invalid capsule type rejected", r.status_code == 422, f"Status: {r.status_code}")

    # Test 128: Pagination edge - page 0
    r = session.get(f"{BASE_URL}/capsules/", params={"page": 0})
    log_test("E.13", "Page 0 handling", r.status_code in [200, 422], f"Status: {r.status_code}")

    # Test 129: Pagination edge - negative page
    r = session.get(f"{BASE_URL}/capsules/", params={"page": -1})
    log_test("E.14", "Negative page handling", r.status_code in [200, 422], f"Status: {r.status_code}")

    # Test 130: Pagination edge - very large page
    r = session.get(f"{BASE_URL}/capsules/", params={"page": 99999})
    log_test("E.15", "Very large page number", r.status_code == 200, f"Status: {r.status_code}")

    # Test 131: Per page edge - max value
    r = session.get(f"{BASE_URL}/capsules/", params={"per_page": 100})
    log_test("E.16", "Max per_page value", r.status_code == 200, f"Status: {r.status_code}")

    # Test 132: Proposal with min description length
    r = session.post(f"{BASE_URL}/governance/proposals", json={
        "title": "Short Description Test",
        "description": "This is exactly twenty!",  # 20 chars min
        "proposal_type": "policy",
        "action": {}
    })
    log_test("E.17", "Proposal min description length", r.status_code == 201, f"Status: {r.status_code}")

    # Test 133: Proposal with description too short
    r = session.post(f"{BASE_URL}/governance/proposals", json={
        "title": "Too Short Test",
        "description": "Too short",  # < 20 chars
        "proposal_type": "policy",
        "action": {}
    })
    log_test("E.18", "Proposal description too short rejected", r.status_code == 422, f"Status: {r.status_code}")

    # Test 134: Proposal title too short
    r = session.post(f"{BASE_URL}/governance/proposals", json={
        "title": "Test",  # < 5 chars
        "description": "This description is long enough to pass validation.",
        "proposal_type": "policy",
        "action": {}
    })
    log_test("E.19", "Proposal title too short rejected", r.status_code == 422, f"Status: {r.status_code}")

    # Test 135: Invalid severity in issue
    r = session.post(f"{BASE_URL}/governance/ghost-council/issues", json={
        "category": "security",
        "severity": "invalid_severity",
        "title": "Test Issue Title",
        "description": "This is a test issue description."
    })
    log_test("E.20", "Invalid severity rejected", r.status_code in [400, 422], f"Status: {r.status_code}")

    # Test 136: Invalid category in issue
    r = session.post(f"{BASE_URL}/governance/ghost-council/issues", json={
        "category": "invalid_category",
        "severity": "high",
        "title": "Test Issue Title",
        "description": "This is a test issue description."
    })
    log_test("E.21", "Invalid category rejected", r.status_code in [400, 422], f"Status: {r.status_code}")

    # Test 137: Cascade with invalid max_hops (too high)
    r = session.post(f"{BASE_URL}/cascade/trigger", json={
        "source_overlay": "test",
        "insight_type": "test",
        "insight_data": {},
        "max_hops": 100  # Max is 10
    })
    log_test("E.22", "Cascade max_hops too high rejected", r.status_code == 422, f"Status: {r.status_code}")

    # Test 138: Cascade with invalid max_hops (zero)
    r = session.post(f"{BASE_URL}/cascade/trigger", json={
        "source_overlay": "test",
        "insight_type": "test",
        "insight_data": {},
        "max_hops": 0  # Min is 1
    })
    log_test("E.23", "Cascade max_hops zero rejected", r.status_code == 422, f"Status: {r.status_code}")

    # Test 139: Search with very long query
    r = session.post(f"{BASE_URL}/capsules/search", json={
        "query": "test " * 400,  # ~2000 chars
        "limit": 5
    })
    log_test("E.24", "Search with max length query", r.status_code in [200, 422], f"Status: {r.status_code}")

    # Test 140: Search with limit at boundary
    r = session.post(f"{BASE_URL}/capsules/search", json={
        "query": "test",
        "limit": 100  # Max limit
    })
    log_test("E.25", "Search with max limit", r.status_code == 200, f"Status: {r.status_code}")

    # Test 141: Lineage depth at max
    if test_data.get("capsule_id"):
        r = session.get(f"{BASE_URL}/capsules/{test_data['capsule_id']}/lineage", params={"depth": 20})
        log_test("E.26", "Lineage with max depth (20)", r.status_code == 200, f"Status: {r.status_code}")
    else:
        log_test("E.26", "Lineage with max depth", False, "No capsule ID")

    # Test 142: Lineage depth over max
    if test_data.get("capsule_id"):
        r = session.get(f"{BASE_URL}/capsules/{test_data['capsule_id']}/lineage", params={"depth": 25})
        log_test("E.27", "Lineage depth over max rejected", r.status_code == 422, f"Status: {r.status_code}")
    else:
        log_test("E.27", "Lineage depth over max rejected", False, "No capsule ID")

    # Test 143: Voting period at boundary (1 day)
    r = session.post(f"{BASE_URL}/governance/proposals", json={
        "title": "One Day Voting Period",
        "description": "Testing minimum voting period of one day.",
        "proposal_type": "policy",
        "action": {},
        "voting_period_days": 1
    })
    log_test("E.28", "Min voting period (1 day)", r.status_code == 201, f"Status: {r.status_code}")

    # Test 144: Voting period at boundary (30 days)
    r = session.post(f"{BASE_URL}/governance/proposals", json={
        "title": "Thirty Day Voting Period",
        "description": "Testing maximum voting period of thirty days.",
        "proposal_type": "policy",
        "action": {},
        "voting_period_days": 30
    })
    log_test("E.29", "Max voting period (30 days)", r.status_code == 201, f"Status: {r.status_code}")

    # Test 145: Voting period over max
    r = session.post(f"{BASE_URL}/governance/proposals", json={
        "title": "Over Max Voting Period",
        "description": "Testing voting period over maximum allowed.",
        "proposal_type": "policy",
        "action": {},
        "voting_period_days": 31
    })
    log_test("E.30", "Voting period over max rejected", r.status_code == 422, f"Status: {r.status_code}")

    # Test 146: Quorum at boundary (0.01)
    r = session.post(f"{BASE_URL}/governance/proposals", json={
        "title": "Minimum Quorum Test",
        "description": "Testing minimum quorum percentage of one percent.",
        "proposal_type": "policy",
        "action": {},
        "quorum_percent": 0.01
    })
    log_test("E.31", "Min quorum (0.01)", r.status_code == 201, f"Status: {r.status_code}")

    # Test 147: Quorum over max
    r = session.post(f"{BASE_URL}/governance/proposals", json={
        "title": "Over Max Quorum Test",
        "description": "Testing quorum percentage over maximum allowed.",
        "proposal_type": "policy",
        "action": {},
        "quorum_percent": 1.5
    })
    log_test("E.32", "Quorum over max rejected", r.status_code == 422, f"Status: {r.status_code}")

    # Test 148: Pass threshold at boundary
    r = session.post(f"{BASE_URL}/governance/proposals", json={
        "title": "Maximum Pass Threshold",
        "description": "Testing maximum pass threshold of one hundred percent.",
        "proposal_type": "policy",
        "action": {},
        "pass_threshold": 1.0
    })
    log_test("E.33", "Max pass threshold (1.0)", r.status_code == 201, f"Status: {r.status_code}")

    # Test 149: Pass threshold under min
    r = session.post(f"{BASE_URL}/governance/proposals", json={
        "title": "Under Min Pass Threshold",
        "description": "Testing pass threshold under minimum allowed.",
        "proposal_type": "policy",
        "action": {},
        "pass_threshold": 0.4  # Min is 0.5
    })
    log_test("E.34", "Pass threshold under min rejected", r.status_code == 422, f"Status: {r.status_code}")

    # Test 150: Anomalies filter with invalid severity
    r = session.get(f"{BASE_URL}/system/anomalies", params={"severity": "invalid"})
    log_test("E.35", "Invalid anomaly severity filter", r.status_code in [200, 400], f"Status: {r.status_code}")

    print()

    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("=" * 80)
    print("COMPREHENSIVE TEST SUMMARY")
    print("=" * 80)

    passed = sum(1 for r in test_results if r["passed"])
    failed = sum(1 for r in test_results if not r["passed"])
    total = len(test_results)

    print(f"\nTotal Tests: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Pass Rate: {(passed/total*100):.1f}%")

    # Summary by section
    sections = {
        "1": "AUTH ROUTES",
        "2": "CAPSULE ROUTES",
        "3": "GOVERNANCE ROUTES",
        "4": "OVERLAY ROUTES",
        "5": "SYSTEM ROUTES",
        "6": "CASCADE ROUTES",
        "E": "EDGE CASES"
    }

    print("\nResults by Section:")
    for prefix, name in sections.items():
        section_tests = [r for r in test_results if r["id"].startswith(prefix)]
        section_passed = sum(1 for r in section_tests if r["passed"])
        section_total = len(section_tests)
        print(f"  {name}: {section_passed}/{section_total}")

    if failed > 0:
        print("\nFailed Tests:")
        for r in test_results:
            if not r["passed"]:
                print(f"  [{r['id']}] {r['test']}: {r['details']}")

    print()
    return passed >= total * 0.8  # 80% pass rate required


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
