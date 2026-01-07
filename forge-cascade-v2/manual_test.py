"""
Forge V3 - Manual Feature Test Suite
Tests key features with proper rate limiting delays.
"""
import requests
import time

BASE_URL = 'http://localhost:8001'
session = requests.Session()

results = {'passed': 0, 'failed': 0, 'tests': []}

def test(category, name, condition, details=''):
    status = 'PASS' if condition else 'FAIL'
    results['passed' if condition else 'failed'] += 1
    results['tests'].append({'category': category, 'name': name, 'status': status, 'details': details})
    icon = '[PASS]' if condition else '[FAIL]'
    print(f'{icon} [{category}] {name}')
    if details and not condition:
        print(f'       {details[:200]}')

print('=' * 60)
print('FORGE V3 COMPREHENSIVE FEATURE TESTS')
print('=' * 60)

# 1. CORE TESTS
print('\n--- CORE TESTS ---')
r = requests.get(f'{BASE_URL}/health')
test('Core', 'Health endpoint', r.status_code == 200)
time.sleep(0.5)

r = requests.get(f'{BASE_URL}/openapi.json')
test('Core', 'OpenAPI docs', r.status_code == 200 and 'paths' in r.json())
time.sleep(0.5)

# 2. AUTHENTICATION
print('\n--- AUTHENTICATION ---')
import os
ADMIN_PWD = os.environ.get('SEED_ADMIN_PASSWORD', 'admin123')
r = session.post(f'{BASE_URL}/api/v1/auth/login',
    json={'username': 'admin', 'password': ADMIN_PWD}, timeout=30)
test('Auth', 'Admin login', r.status_code == 200, f'Status: {r.status_code}')
has_cookies = 'access_token' in session.cookies
test('Auth', 'Cookie authentication', has_cookies, f'Cookies: {list(session.cookies.keys())}')
time.sleep(1)

# Test me endpoint
r = session.get(f'{BASE_URL}/api/v1/auth/me')
test('Auth', 'Get current user', r.status_code == 200)
if r.status_code == 200:
    user = r.json().get('data', r.json())
    print(f'       User: {user.get("username", "unknown")}')
time.sleep(1)

# 3. CAPSULES
print('\n--- CAPSULES ---')
r = session.get(f'{BASE_URL}/api/v1/capsules')
test('Capsules', 'List capsules', r.status_code == 200)
time.sleep(1)

# Create capsule
capsule_data = {
    'content': 'Test capsule created during feature testing',
    'capsule_type': 'memory',
    'source': 'test_script',
    'tags': ['test', 'verification']
}
r = session.post(f'{BASE_URL}/api/v1/capsules', json=capsule_data, timeout=30)
test('Capsules', 'Create capsule', r.status_code in [200, 201], f'Status: {r.status_code}')
capsule_id = None
if r.status_code in [200, 201]:
    data = r.json()
    capsule_id = data.get('data', data).get('id')
    print(f'       Created: {capsule_id}')
time.sleep(1)

# Get capsule
if capsule_id:
    r = session.get(f'{BASE_URL}/api/v1/capsules/{capsule_id}')
    test('Capsules', 'Get capsule by ID', r.status_code == 200)
    time.sleep(1)

# 4. GOVERNANCE
print('\n--- GOVERNANCE ---')
r = session.get(f'{BASE_URL}/api/v1/governance/proposals')
test('Governance', 'List proposals', r.status_code == 200)
time.sleep(1)

# Create proposal
proposal_data = {
    'title': 'Test Proposal for Feature Verification',
    'description': 'This is a test proposal to verify the governance system works correctly.',
    'proposal_type': 'policy',
    'action': {}
}
r = session.post(f'{BASE_URL}/api/v1/governance/proposals', json=proposal_data, timeout=30)
test('Governance', 'Create proposal', r.status_code in [200, 201], f'Status: {r.status_code}')
proposal_id = None
if r.status_code in [200, 201]:
    data = r.json()
    proposal_id = data.get('data', data).get('id')
    print(f'       Created: {proposal_id}')
time.sleep(1)

# Submit proposal to start voting
if proposal_id:
    r = session.post(f'{BASE_URL}/api/v1/governance/proposals/{proposal_id}/submit', timeout=30)
    test('Governance', 'Submit proposal for voting', r.status_code in [200, 201], f'Status: {r.status_code}')
    if r.status_code in [200, 201]:
        data = r.json()
        print(f'       Status: {data.get("status", "unknown")}')
    time.sleep(1)

# Vote on proposal
if proposal_id:
    r = session.post(f'{BASE_URL}/api/v1/governance/proposals/{proposal_id}/vote',
        json={'choice': 'APPROVE', 'reason': 'Testing voting system'}, timeout=30)
    test('Governance', 'Vote on proposal', r.status_code in [200, 201, 409], f'Status: {r.status_code}')
    time.sleep(1)

# Governance metrics
r = session.get(f'{BASE_URL}/api/v1/governance/metrics')
test('Governance', 'Governance metrics', r.status_code == 200)
time.sleep(1)

# 5. GHOST COUNCIL
print('\n--- GHOST COUNCIL ---')
r = session.get(f'{BASE_URL}/api/v1/governance/ghost-council/members')
test('GhostCouncil', 'Get members', r.status_code == 200)
if r.status_code == 200:
    members = r.json()
    print(f'       Members: {len(members) if isinstance(members, list) else "N/A"}')
time.sleep(1)

r = session.get(f'{BASE_URL}/api/v1/governance/ghost-council/stats')
test('GhostCouncil', 'Get stats', r.status_code == 200)
time.sleep(1)

r = session.get(f'{BASE_URL}/api/v1/governance/ghost-council/issues')
test('GhostCouncil', 'Get issues', r.status_code == 200)
time.sleep(1)

# Get recommendation for proposal
if proposal_id:
    r = session.get(f'{BASE_URL}/api/v1/governance/proposals/{proposal_id}/ghost-council?use_ai=false')
    test('GhostCouncil', 'Proposal recommendation', r.status_code == 200, f'Status: {r.status_code}')
time.sleep(1)

# 6. OVERLAYS
print('\n--- OVERLAYS ---')
r = session.get(f'{BASE_URL}/api/v1/overlays')
test('Overlays', 'List overlays', r.status_code == 200)
if r.status_code == 200:
    data = r.json()
    overlays = data.get('data', data) if isinstance(data, dict) else data
    print(f'       Overlays: {len(overlays) if overlays else 0}')
time.sleep(1)

# 7. SYSTEM/IMMUNE
print('\n--- SYSTEM/IMMUNE ---')
r = session.get(f'{BASE_URL}/api/v1/system/health')
test('System', 'System health', r.status_code == 200)
time.sleep(1)

r = session.get(f'{BASE_URL}/api/v1/system/status')
test('System', 'System status', r.status_code == 200)
time.sleep(1)

r = session.get(f'{BASE_URL}/api/v1/system/metrics')
test('System', 'System metrics', r.status_code == 200)
time.sleep(1)

# 8. EVENTS
print('\n--- EVENTS ---')
r = session.get(f'{BASE_URL}/api/v1/system/audit')
test('Events', 'Audit log', r.status_code == 200)
time.sleep(1)

r = session.get(f'{BASE_URL}/api/v1/system/events')
test('Events', 'Recent events', r.status_code == 200)
time.sleep(1)

# 9. TRUST
print('\n--- TRUST ---')
r = session.get(f'{BASE_URL}/api/v1/auth/me')
if r.status_code == 200:
    user_data = r.json().get('data', r.json())
    trust_level = user_data.get('trust_level', user_data.get('trust_flame'))
    test('Trust', 'User has trust level', trust_level is not None, f'Trust: {trust_level}')
time.sleep(1)

# 10. EDGE CASES
print('\n--- EDGE CASES ---')
r = requests.get(f'{BASE_URL}/api/v1/nonexistent')
test('EdgeCases', '404 handling', r.status_code == 404)
time.sleep(0.5)

r = session.get(f'{BASE_URL}/api/v1/capsules/nonexistent-id')
test('EdgeCases', 'Invalid capsule ID', r.status_code in [404, 422])
time.sleep(0.5)

r = session.post(f'{BASE_URL}/api/v1/capsules', data='invalid json', headers={'Content-Type': 'application/json'})
test('EdgeCases', 'Malformed JSON handling', r.status_code in [400, 422])
time.sleep(0.5)

# SUMMARY
print('\n' + '=' * 60)
print('TEST SUMMARY')
print('=' * 60)
total = results['passed'] + results['failed']
print(f'Total: {total}')
print(f'Passed: {results["passed"]}')
print(f'Failed: {results["failed"]}')
print(f'Pass Rate: {100*results["passed"]/total:.1f}%')
print()

if results['failed'] > 0:
    print('Failed tests:')
    for t in results['tests']:
        if t['status'] == 'FAIL':
            print(f'  - [{t["category"]}] {t["name"]}: {t.get("details", "")}')
