#!/usr/bin/env python3
"""
Ghost Council Live Test Suite

Tests all Ghost Council functionality:
1. Member listing and stats
2. Serious issue reporting
3. Issue deliberation
4. Issue resolution
5. Proposal recommendations
"""

import requests
import json
import time
import os

BASE_URL = os.environ.get("TEST_API_URL", "http://localhost:8000")

# Test results tracking
results = {"passed": 0, "failed": 0, "tests": []}


def log_test(name, passed, details=""):
    status = "PASS" if passed else "FAIL"
    results["passed" if passed else "failed"] += 1
    results["tests"].append({"name": name, "passed": passed, "details": details})
    print(f"  [{status}] {name}")
    if details and not passed:
        print(f"        Details: {details}")


def get_session(username, password):
    """Create authenticated session."""
    session = requests.Session()
    response = session.post(
        f"{BASE_URL}/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    if response.status_code == 200:
        csrf_token = response.json().get("csrf_token")
        return session, {"X-CSRF-Token": csrf_token}
    return None, None


print("=" * 70)
print("GHOST COUNCIL COMPREHENSIVE TEST SUITE")
print("=" * 70)

# Get password from environment or use generated one
admin_password = os.environ.get("SEED_ADMIN_PASSWORD")
oracle_password = os.environ.get("SEED_ORACLE_PASSWORD")

if not admin_password or not oracle_password:
    # Try to read from .seed_credentials
    creds_file = os.path.join(os.path.dirname(__file__), "scripts", ".seed_credentials")
    if os.path.exists(creds_file):
        print(f"\nReading credentials from {creds_file}")
        with open(creds_file) as f:
            for line in f:
                if line.startswith("SEED_ADMIN_PASSWORD="):
                    admin_password = line.strip().split("=", 1)[1]
                elif line.startswith("SEED_ORACLE_PASSWORD="):
                    oracle_password = line.strip().split("=", 1)[1]

if not admin_password or not oracle_password:
    print("\nERROR: Could not find credentials.")
    print("Please set SEED_ADMIN_PASSWORD and SEED_ORACLE_PASSWORD environment variables")
    print("Or run: python scripts/seed_data.py")
    exit(1)

# =============================================================================
# SECTION 1: AUTHENTICATION
# =============================================================================
print("\n" + "=" * 70)
print("1. AUTHENTICATION")
print("=" * 70)

# Login as admin (CORE)
admin_session, admin_headers = get_session("admin", admin_password)
if admin_session:
    log_test("Admin (CORE) login", True)
else:
    log_test("Admin (CORE) login", False, "Could not authenticate")
    print("\nFATAL: Cannot continue without admin authentication")
    exit(1)

# Login as oracle (TRUSTED)
oracle_session, oracle_headers = get_session("oracle", oracle_password)
if oracle_session:
    log_test("Oracle (TRUSTED) login", True)
else:
    log_test("Oracle (TRUSTED) login", False, "Could not authenticate")

# =============================================================================
# SECTION 2: GHOST COUNCIL MEMBERS
# =============================================================================
print("\n" + "=" * 70)
print("2. GHOST COUNCIL MEMBERS")
print("=" * 70)

# Get Ghost Council members
response = admin_session.get(
    f"{BASE_URL}/api/v1/governance/ghost-council/members",
    headers=admin_headers,
)
log_test("Get Ghost Council members", response.status_code == 200, f"Status: {response.status_code}")

if response.status_code == 200:
    members = response.json()
    log_test("Ghost Council has members", len(members) > 0, f"Members: {len(members)}")
    print("\n  Ghost Council Members:")
    for member in members:
        print(f"    - {member.get('name')}: {member.get('role')}")
        print(f"      Expertise: {', '.join(member.get('expertise', []))}")

# =============================================================================
# SECTION 3: GHOST COUNCIL STATISTICS
# =============================================================================
print("\n" + "=" * 70)
print("3. GHOST COUNCIL STATISTICS")
print("=" * 70)

response = admin_session.get(
    f"{BASE_URL}/api/v1/governance/ghost-council/stats",
    headers=admin_headers,
)
log_test("Get Ghost Council stats", response.status_code == 200, f"Status: {response.status_code}")

if response.status_code == 200:
    stats = response.json()
    print("\n  Ghost Council Statistics:")
    for key, value in stats.items():
        print(f"    - {key}: {value}")

# =============================================================================
# SECTION 4: SERIOUS ISSUE REPORTING
# =============================================================================
print("\n" + "=" * 70)
print("4. SERIOUS ISSUE REPORTING")
print("=" * 70)

# Report a serious security issue
security_issue = {
    "title": "Critical Security Vulnerability Detected",
    "description": "A potential SQL injection vulnerability was discovered in the capsule search endpoint. This could allow unauthorized access to sensitive data.",
    "severity": "critical",
    "category": "security",
    "affected_entities": ["capsule_repository", "search_service"],
}

response = admin_session.post(
    f"{BASE_URL}/api/v1/governance/ghost-council/issues",
    headers=admin_headers,
    json=security_issue,
)
log_test("Report critical security issue", response.status_code in [200, 201], f"Status: {response.status_code}")

if response.status_code in [200, 201]:
    issue1 = response.json()
    issue1_id = issue1.get("id") or issue1.get("issue_id")
    print(f"\n  Created Issue ID: {issue1_id}")
    print(f"  Status: {issue1.get('status')}")
    if issue1.get("deliberation"):
        print(f"  Ghost Council Deliberation:")
        delib = issue1.get("deliberation", {})
        print(f"    Severity Assessment: {delib.get('severity_assessment')}")
        print(f"    Recommended Action: {delib.get('recommended_action')}")
        if delib.get("member_opinions"):
            print("    Member Opinions:")
            for opinion in delib.get("member_opinions", []):
                print(f"      - {opinion.get('member')}: {opinion.get('stance')}")
else:
    issue1_id = None
    print(f"  Error: {response.text[:200]}")

# Report a governance issue
governance_issue = {
    "title": "Trust Score Manipulation Detected",
    "description": "Multiple accounts appear to be artificially inflating trust scores through coordinated voting patterns. This threatens the integrity of the governance system.",
    "severity": "high",
    "category": "governance",
    "affected_entities": ["voting_system", "trust_service"],
}

response = admin_session.post(
    f"{BASE_URL}/api/v1/governance/ghost-council/issues",
    headers=admin_headers,
    json=governance_issue,
)
log_test("Report governance integrity issue", response.status_code in [200, 201], f"Status: {response.status_code}")

if response.status_code in [200, 201]:
    issue2 = response.json()
    issue2_id = issue2.get("id") or issue2.get("issue_id")
    print(f"\n  Created Issue ID: {issue2_id}")
else:
    issue2_id = None

# Report a system stability issue
stability_issue = {
    "title": "Cascade Pipeline Performance Degradation",
    "description": "The 7-phase cascade pipeline is experiencing significant latency spikes, with some executions taking over 30 seconds. This is impacting system responsiveness.",
    "severity": "medium",
    "category": "system",
    "affected_entities": ["cascade_pipeline", "overlay_manager"],
}

response = admin_session.post(
    f"{BASE_URL}/api/v1/governance/ghost-council/issues",
    headers=admin_headers,
    json=stability_issue,
)
log_test("Report performance issue", response.status_code in [200, 201], f"Status: {response.status_code}")

if response.status_code in [200, 201]:
    issue3 = response.json()
    issue3_id = issue3.get("id") or issue3.get("issue_id")
else:
    issue3_id = None

# =============================================================================
# SECTION 5: VIEW ACTIVE ISSUES
# =============================================================================
print("\n" + "=" * 70)
print("5. VIEW ACTIVE ISSUES")
print("=" * 70)

# Need TRUSTED level to view issues
if oracle_session:
    response = oracle_session.get(
        f"{BASE_URL}/api/v1/governance/ghost-council/issues",
        headers=oracle_headers,
    )
    log_test("Get active issues (TRUSTED user)", response.status_code == 200, f"Status: {response.status_code}")

    if response.status_code == 200:
        issues = response.json()
        print(f"\n  Active Issues: {len(issues)}")
        for issue in issues[:5]:  # Show first 5
            print(f"\n    Issue: {issue.get('title', 'N/A')[:50]}")
            print(f"    Severity: {issue.get('severity')}")
            print(f"    Status: {issue.get('status')}")
            print(f"    Category: {issue.get('category')}")

# =============================================================================
# SECTION 6: GHOST COUNCIL DELIBERATION
# =============================================================================
print("\n" + "=" * 70)
print("6. GHOST COUNCIL DELIBERATION")
print("=" * 70)

# The Ghost Council should have automatically deliberated on reported issues
# Let's check the deliberation details

if issue1_id and oracle_session:
    # Get issue details to see deliberation
    response = oracle_session.get(
        f"{BASE_URL}/api/v1/governance/ghost-council/issues",
        headers=oracle_headers,
    )

    if response.status_code == 200:
        issues = response.json()
        for issue in issues:
            if issue.get("id") == issue1_id or issue.get("issue_id") == issue1_id:
                # Check if Ghost Council has deliberated on this issue
                has_opinion = issue.get("has_ghost_council_opinion", False)
                if has_opinion:
                    log_test("Ghost Council deliberated on issue", True)
                    print(f"\n  Deliberation for: {issue.get('title', 'N/A')[:40]}")
                    print(f"    Category: {issue.get('category', 'N/A')}")
                    print(f"    Severity: {issue.get('severity', 'N/A')}")
                    print(f"    Has Ghost Council Opinion: Yes")
                else:
                    log_test("Ghost Council deliberated on issue", False, "No deliberation found")
                break

# =============================================================================
# SECTION 7: ISSUE RESOLUTION
# =============================================================================
print("\n" + "=" * 70)
print("7. ISSUE RESOLUTION")
print("=" * 70)

if issue3_id:  # Resolve the performance issue
    resolution_data = {
        "resolution": "Implemented caching layer for analysis phase and optimized validation queries. Pipeline latency reduced by 60%.",
        "actions_taken": [
            "Added Redis cache for intermediate results",
            "Optimized Neo4j queries in validation phase",
            "Increased connection pool size"
        ]
    }

    response = admin_session.post(
        f"{BASE_URL}/api/v1/governance/ghost-council/issues/{issue3_id}/resolve",
        headers=admin_headers,
        json=resolution_data,
    )
    log_test("Resolve performance issue", response.status_code == 200, f"Status: {response.status_code}")

    if response.status_code == 200:
        resolved = response.json()
        print(f"\n  Resolved Issue: {resolved.get('title', 'N/A')[:40]}")
        print(f"  Resolution: {resolved.get('resolution', 'N/A')[:60]}...")
        print(f"  Status: {resolved.get('status')}")
else:
    log_test("Resolve performance issue", False, "No issue ID available")

# =============================================================================
# SECTION 8: PROPOSAL RECOMMENDATIONS
# =============================================================================
print("\n" + "=" * 70)
print("8. PROPOSAL GHOST COUNCIL RECOMMENDATIONS")
print("=" * 70)

# First, get existing proposals
response = admin_session.get(
    f"{BASE_URL}/api/v1/governance/proposals",
    headers=admin_headers,
)

if response.status_code == 200:
    proposals_data = response.json()
    proposals = proposals_data.get("items", proposals_data) if isinstance(proposals_data, dict) else proposals_data

    if proposals and len(proposals) > 0:
        proposal = proposals[0]
        proposal_id = proposal.get("id")

        print(f"\n  Testing with proposal: {proposal.get('title', 'N/A')[:40]}")

        # Get Ghost Council recommendation
        response = admin_session.get(
            f"{BASE_URL}/api/v1/governance/proposals/{proposal_id}/ghost-council",
            headers=admin_headers,
        )
        log_test("Get proposal recommendation", response.status_code == 200, f"Status: {response.status_code}")

        if response.status_code == 200:
            recommendation = response.json()
            print(f"\n  Ghost Council Recommendation:")
            print(f"    Recommendation: {recommendation.get('recommendation')}")
            print(f"    Confidence: {recommendation.get('confidence', 0) * 100:.1f}%")
            print(f"    Reasoning: {recommendation.get('reasoning', 'N/A')[:100]}...")

            hist = recommendation.get("historical_patterns", {})
            if hist:
                print(f"    Historical Context:")
                print(f"      Similar proposals: {hist.get('similar_proposals', 0)}")
                print(f"      Typical outcome: {hist.get('typical_outcome', 'N/A')}")
    else:
        log_test("Get proposal recommendation", False, "No proposals found")
else:
    log_test("Get proposals list", False, f"Status: {response.status_code}")

# =============================================================================
# SECTION 9: EDGE CASES
# =============================================================================
print("\n" + "=" * 70)
print("9. EDGE CASES")
print("=" * 70)

# Test invalid severity
invalid_issue = {
    "title": "Test Issue Here",
    "description": "This is a test description that is long enough.",
    "severity": "INVALID_SEVERITY",
    "category": "security",
}
response = admin_session.post(
    f"{BASE_URL}/api/v1/governance/ghost-council/issues",
    headers=admin_headers,
    json=invalid_issue,
)
log_test("Reject invalid severity", response.status_code == 400, f"Status: {response.status_code}")

# Test empty title
empty_issue = {
    "title": "",
    "description": "Test description that is long enough to pass validation.",
    "severity": "low",
    "category": "security",
}
response = admin_session.post(
    f"{BASE_URL}/api/v1/governance/ghost-council/issues",
    headers=admin_headers,
    json=empty_issue,
)
log_test("Reject empty title", response.status_code == 422, f"Status: {response.status_code}")

# Test resolving non-existent issue
response = admin_session.post(
    f"{BASE_URL}/api/v1/governance/ghost-council/issues/non-existent-id/resolve",
    headers=admin_headers,
    json={"resolution": "This is a valid resolution that is long enough."},
)
log_test("Reject resolving non-existent issue", response.status_code == 404, f"Status: {response.status_code}")

# =============================================================================
# SUMMARY
# =============================================================================
print("\n" + "=" * 70)
print("TEST SUMMARY")
print("=" * 70)
print(f"\nTotal Tests: {results['passed'] + results['failed']}")
print(f"Passed: {results['passed']}")
print(f"Failed: {results['failed']}")
print(f"Pass Rate: {results['passed'] / (results['passed'] + results['failed']) * 100:.1f}%")

if results["failed"] > 0:
    print("\nFailed Tests:")
    for test in results["tests"]:
        if not test["passed"]:
            print(f"  - {test['name']}")
            if test["details"]:
                print(f"    Details: {test['details']}")

print("\n" + "=" * 70)
print("GHOST COUNCIL TEST COMPLETE")
print("=" * 70)
