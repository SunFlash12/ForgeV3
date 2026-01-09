"""
Forge V3 Quick Comprehensive Test Suite
"""
import requests
import uuid
import time
import os
import sys

BASE = os.environ.get("TEST_API_URL", "http://localhost:8001/api/v1")

# SECURITY FIX: Require password from environment, no hardcoded defaults
ADMIN_PASSWORD = os.environ.get("SEED_ADMIN_PASSWORD")
if not ADMIN_PASSWORD:
    print("ERROR: SEED_ADMIN_PASSWORD environment variable is required")
    print("Set it with: export SEED_ADMIN_PASSWORD=<your-secure-password>")
    sys.exit(1)

session = requests.Session()
passed = 0
failed = 0
total = 0

def test(name, condition, details=''):
    global passed, failed, total
    total += 1
    if condition:
        print(f'[PASS] {name}')
        passed += 1
    else:
        print(f'[FAIL] {name} - {details}')
        failed += 1

print('=' * 70)
print('FORGE V3 COMPREHENSIVE TEST SUITE')
print('=' * 70)

# ===== CORE ARCHITECTURE =====
print('\n--- CORE ARCHITECTURE ---')
r = requests.get(f'{BASE.replace("/api/v1", "")}/health')
test('Health endpoint', r.status_code == 200)

r = requests.get(f'{BASE.replace("/api/v1", "")}/openapi.json')
test('OpenAPI documentation', r.status_code == 200 and 'paths' in r.json())

# ===== AUTHENTICATION =====
print('\n--- AUTHENTICATION ---')
r = session.post(f'{BASE}/auth/login', json={'username': 'admin', 'password': ADMIN_PASSWORD})
test('Admin login', r.status_code == 200, f'{r.status_code}')

r = session.get(f'{BASE}/auth/me')
user_data = r.json() if r.status_code == 200 else {}
test('Get current user', r.status_code == 200 and 'id' in user_data)
test('Admin has CORE trust', user_data.get('trust_level') == 'CORE', f'{user_data.get("trust_level")}')

r = session.get(f'{BASE}/auth/me/trust')
test('Get user trust details', r.status_code == 200)

r = session.post(f'{BASE}/auth/refresh')
test('Token refresh', r.status_code == 200)

# ===== CAPSULES =====
print('\n--- CAPSULES & KNOWLEDGE ENGINE ---')
capsule_ids = []
for ctype in ['KNOWLEDGE', 'DECISION', 'MEMORY', 'INSIGHT']:
    r = session.post(f'{BASE}/capsules/', json={'content': f'Test capsule of type {ctype}', 'type': ctype})
    if r.status_code == 201:
        capsule_ids.append(r.json().get('id'))
    test(f'Create {ctype} capsule', r.status_code == 201, f'{r.status_code}')

r = session.get(f'{BASE}/capsules/')
capsule_list = r.json() if r.status_code == 200 else []
test('List capsules', r.status_code == 200 and len(capsule_list) > 0, f'{r.status_code}')

r = session.get(f'{BASE}/capsules/?page=1&per_page=5')
test('List with pagination', r.status_code == 200)

r = session.get(f'{BASE}/capsules/?type=KNOWLEDGE')
test('Filter by type', r.status_code == 200)

if capsule_ids:
    r = session.get(f'{BASE}/capsules/{capsule_ids[0]}')
    test('Get capsule by ID', r.status_code == 200)

    r = session.patch(f'{BASE}/capsules/{capsule_ids[0]}', json={'content': 'Updated content'})
    test('Update capsule', r.status_code == 200)

    r = session.get(f'{BASE}/capsules/{capsule_ids[0]}/lineage')
    test('Get capsule lineage', r.status_code in [200, 404])

r = session.post(f'{BASE}/capsules/search', json={'query': 'test', 'limit': 5})
test('Semantic search', r.status_code == 200)

# Edge cases
r = session.post(f'{BASE}/capsules/', json={'content': '', 'type': 'KNOWLEDGE'})
test('Empty content rejection', r.status_code == 422)

r = session.post(f'{BASE}/capsules/', json={'content': 'test', 'type': 'INVALID'})
test('Invalid type rejection', r.status_code == 422)

# ===== GOVERNANCE =====
print('\n--- GOVERNANCE ---')
r = session.get(f'{BASE}/governance/proposals')
test('List proposals', r.status_code == 200)

r = session.post(f'{BASE}/governance/proposals', json={
    'title': f'Test Proposal {uuid.uuid4().hex[:8]}',
    'description': 'Test proposal for governance system verification',
    'type': 'policy',
    'payload': {'action': 'test', 'value': 123}
})
proposal_id = r.json().get('id') if r.status_code == 201 else None
test('Create proposal', r.status_code == 201, f'{r.status_code}')

if proposal_id:
    r = session.get(f'{BASE}/governance/proposals/{proposal_id}')
    test('Get proposal by ID', r.status_code == 200)

    r = session.post(f'{BASE}/governance/proposals/{proposal_id}/submit')
    test('Submit proposal', r.status_code in [200, 400])

    r = session.post(f'{BASE}/governance/proposals/{proposal_id}/vote', json={'decision': 'for', 'reasoning': 'Test vote'})
    test('Cast vote', r.status_code in [200, 201, 400, 422])

r = session.get(f'{BASE}/governance/proposals?status=draft')
test('Filter proposals by status', r.status_code == 200)

r = session.get(f'{BASE}/governance/metrics')
test('Governance metrics', r.status_code == 200)

r = session.get(f'{BASE}/governance/policies')
test('List policies', r.status_code == 200)

# ===== GHOST COUNCIL =====
print('\n--- GHOST COUNCIL ---')
r = session.get(f'{BASE}/governance/ghost-council/members')
members = r.json() if r.status_code == 200 else []
test('Get Ghost Council members', r.status_code == 200 and len(members) > 0, f'{r.status_code}')

r = session.get(f'{BASE}/governance/ghost-council/stats')
test('Get Ghost Council stats', r.status_code == 200)

r = session.get(f'{BASE}/governance/ghost-council/issues')
test('Get Ghost Council issues', r.status_code == 200)

# ===== OVERLAYS =====
print('\n--- OVERLAYS ---')
r = session.get(f'{BASE}/overlays/')
overlays_data = r.json() if r.status_code == 200 else {}
overlays = overlays_data if isinstance(overlays_data, list) else overlays_data.get('overlays', overlays_data.get('items', overlays_data.get('data', [])))
test('List overlays', r.status_code == 200 and len(overlays) > 0, f'{r.status_code}')

r = session.get(f'{BASE}/overlays/active')
test('Active overlays', r.status_code == 200)

if overlays and isinstance(overlays, list):
    overlay_id = overlays[0].get('id') if isinstance(overlays[0], dict) else None
    if overlay_id:
        r = session.get(f'{BASE}/overlays/{overlay_id}')
        test('Get overlay by ID', r.status_code == 200)

        r = session.get(f'{BASE}/overlays/{overlay_id}/metrics')
        test('Get overlay metrics', r.status_code in [200, 404])

# ===== SYSTEM =====
print('\n--- SYSTEM & IMMUNE ---')
r = session.get(f'{BASE}/system/status')
test('System status', r.status_code == 200)

r = session.get(f'{BASE}/system/info')
test('System info', r.status_code == 200)

r = session.get(f'{BASE}/system/metrics')
test('System metrics', r.status_code == 200)

r = session.get(f'{BASE}/system/circuit-breakers')
test('Circuit breakers', r.status_code == 200)

r = session.get(f'{BASE}/system/events')
test('System events', r.status_code == 200)

r = session.get(f'{BASE}/system/events/recent')
test('Recent events', r.status_code == 200)

r = session.get(f'{BASE}/system/anomalies')
test('Anomalies', r.status_code == 200)

r = session.get(f'{BASE}/system/canaries')
test('Canaries', r.status_code == 200)

# ===== AUDIT LOG (Fixed!) =====
print('\n--- AUDIT LOG ---')
r = session.get(f'{BASE}/system/audit')
audit_data = r.json() if r.status_code == 200 else {}
test('Audit log endpoint', r.status_code == 200 and 'items' in audit_data)
if r.status_code == 200:
    print(f'   Total audit entries: {audit_data.get("total", 0)}')

r = session.get(f'{BASE}/system/audit-log')
test('Audit log (alternative)', r.status_code == 200)

# ===== EDGE CASES =====
print('\n--- EDGE CASES ---')
r = session.get(f'{BASE}/capsules/not-a-uuid')
test('Invalid UUID handling', r.status_code in [404, 422])

r = session.get(f'{BASE}/capsules/{uuid.uuid4()}')
test('Non-existent capsule 404', r.status_code == 404)

r = session.post(f'{BASE}/capsules/search', json={'query': "'; DROP TABLE--", 'limit': 5})
test('SQL injection handling', r.status_code != 500)

# ===== SUMMARY =====
print('\n' + '=' * 70)
print(f'TEST SUMMARY')
print(f'=' * 70)
print(f'PASSED: {passed}/{total}')
print(f'FAILED: {failed}/{total}')
print(f'Pass Rate: {100*passed/total:.1f}%')
print('=' * 70)
