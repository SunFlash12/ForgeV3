"""Create the perfect origin capsule for Forge."""
import requests
import json

base_url = 'http://localhost:8000/api/v1'

# Login first
print("Logging in...")
login_resp = requests.post(f'{base_url}/auth/login', json={
    'username': 'forgemaster',
    'password': 'Kn0wl3dge!Gr4ph#2024'
})
print(f"Login status: {login_resp.status_code}")

cookies = login_resp.cookies
csrf_token = login_resp.json()['csrf_token']
access_token = cookies.get('access_token')
print(f"Got access token: {access_token[:50]}...")

# Create the origin capsule
origin_capsule = {
    'title': 'Forge: The Institutional Memory Engine',
    'content': """# Forge: Institutional Memory Engine

## Purpose
Forge is a cognitive architecture designed to preserve knowledge across AI system generations. It solves the fundamental problem of AI systems losing institutional memory during retraining, upgrades, or replacement.

## Core Principles

### 1. Capsules as Atomic Knowledge Units
Knowledge is stored in **Capsules** - versioned, traceable, inheritable containers that:
- Preserve content integrity via cryptographic hashing
- Support symbolic inheritance (lineage tracking)
- Enable semantic discovery through embeddings
- Maintain trust levels for access control

### 2. Overlays for Modular Processing
**Overlays** are specialized processors that execute during the 7-phase pipeline:
- Security Validator (content security)
- ML Intelligence (semantic analysis)
- Governance (consensus voting)
- Lineage Tracker (chain of derivation)
- Graph Algorithms (relationship discovery)

### 3. Trust-Based Security (5 Levels)
- CORE (100): System-critical, full access
- TRUSTED (80): Verified, most operations
- STANDARD (60): Default, basic operations
- SANDBOX (40): Experimental, limited
- QUARANTINE (0): Blocked

### 4. Ghost Council (AI Governance)
An advisory board of AI personas that deliberates on proposals from three perspectives: Optimistic, Balanced, and Critical.

### 5. Isnad (Lineage System)
Every capsule can derive from a parent, creating traceable chains of knowledge evolution. Origin capsules (like this one) have no parent and form the root of lineage trees.

## Architecture Overview

The system flows from Capsules through Overlays and the 7-phase Pipeline to Events stored in the Neo4j Graph, supported by the Ghost Council, Trust System, and Immune System.

This capsule is the **origin** of the Forge knowledge graph - all derived knowledge traces back here.

---
Created: 2026-01-23
Type: KNOWLEDGE (foundational)
Trust: CORE""",
    'type': 'KNOWLEDGE',
    'tags': ['forge', 'architecture', 'origin', 'foundational', 'core'],
    'metadata': {
        'domain': 'system-architecture',
        'version': '1.0.0',
        'is_origin': True,
        'criticality': 'foundational',
        'reviewed_by': ['system-architect'],
        'status': 'canonical'
    }
}

# Create capsule with proper auth
headers = {
    'X-CSRF-Token': csrf_token,
    'Content-Type': 'application/json',
    'Authorization': f'Bearer {access_token}'
}

print("\nCreating origin capsule...")

# Debug: print what we're sending
print(f"Cookies being sent: {dict(cookies)}")
print(f"Headers: {headers}")

# Use a session to ensure cookies are properly managed
session = requests.Session()
session.cookies.update(cookies)

create_resp = session.post(
    f'{base_url}/capsules',
    json=origin_capsule,
    headers=headers
)

print(f'Create Capsule Status: {create_resp.status_code}')
print(json.dumps(create_resp.json(), indent=2))
