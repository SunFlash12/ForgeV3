"""Create the origin capsule directly in Neo4j."""
import asyncio
from neo4j import AsyncGraphDatabase
import uuid
from datetime import datetime

# Database config from .env
NEO4J_URI = "neo4j+s://b76c3818.databases.neo4j.io"
NEO4J_USERNAME = "neo4j"
NEO4J_PASSWORD = "UW-SRZ2dxKkLME2qX2B-vLJlbk3Bw5kClXXY8YqfEHg"
NEO4J_DATABASE = "neo4j"

# User ID from the forgemaster user
CREATOR_ID = "ba21f02f-81b4-4478-a60b-13054b25d181"

# Origin capsule content
CAPSULE = {
    "id": str(uuid.uuid4()),
    "title": "Forge: The Institutional Memory Engine",
    "content": """# Forge: Institutional Memory Engine

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
    "type": "KNOWLEDGE",
    "tags": ["forge", "architecture", "origin", "foundational", "core"],
    "trust_level": "CORE",
    "trust_score": 100.0,
    "status": "active",
    "version": 1,
    "created_at": datetime.utcnow().isoformat() + "Z",
    "updated_at": datetime.utcnow().isoformat() + "Z",
    "created_by": CREATOR_ID,
    "parent_id": None,  # Origin capsule has no parent
    "metadata": {
        "domain": "system-architecture",
        "version": "1.0.0",
        "is_origin": True,
        "criticality": "foundational",
        "reviewed_by": ["system-architect"],
        "status": "canonical"
    }
}


async def create_capsule():
    print("Connecting to Neo4j...")
    driver = AsyncGraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USERNAME, NEO4J_PASSWORD),
        database=NEO4J_DATABASE
    )

    try:
        async with driver.session(database=NEO4J_DATABASE) as session:
            # Create the capsule node
            query = """
            CREATE (c:Capsule {
                id: $id,
                title: $title,
                content: $content,
                type: $type,
                tags: $tags,
                trust_level: $trust_level,
                trust_score: $trust_score,
                status: $status,
                version: $version,
                created_at: datetime($created_at),
                updated_at: datetime($updated_at),
                created_by: $created_by,
                metadata: $metadata_json
            })
            WITH c
            MATCH (u:User {id: $created_by})
            CREATE (u)-[:CREATED]->(c)
            RETURN c.id AS capsule_id, c.title AS title
            """

            import json
            params = {
                "id": CAPSULE["id"],
                "title": CAPSULE["title"],
                "content": CAPSULE["content"],
                "type": CAPSULE["type"],
                "tags": CAPSULE["tags"],
                "trust_level": CAPSULE["trust_level"],
                "trust_score": CAPSULE["trust_score"],
                "status": CAPSULE["status"],
                "version": CAPSULE["version"],
                "created_at": CAPSULE["created_at"],
                "updated_at": CAPSULE["updated_at"],
                "created_by": CAPSULE["created_by"],
                "metadata_json": json.dumps(CAPSULE["metadata"])
            }

            print(f"Creating capsule with ID: {CAPSULE['id']}")
            result = await session.run(query, params)
            record = await result.single()

            if record:
                print(f"SUCCESS! Created capsule:")
                print(f"  ID: {record['capsule_id']}")
                print(f"  Title: {record['title']}")
            else:
                print("WARNING: No relationship created (user may not exist)")
                # Try without the relationship
                query2 = """
                CREATE (c:Capsule {
                    id: $id,
                    title: $title,
                    content: $content,
                    type: $type,
                    tags: $tags,
                    trust_level: $trust_level,
                    trust_score: $trust_score,
                    status: $status,
                    version: $version,
                    created_at: datetime($created_at),
                    updated_at: datetime($updated_at),
                    created_by: $created_by,
                    metadata: $metadata_json
                })
                RETURN c.id AS capsule_id, c.title AS title
                """
                result2 = await session.run(query2, params)
                record2 = await result2.single()
                if record2:
                    print(f"SUCCESS! Created capsule (without user relationship):")
                    print(f"  ID: {record2['capsule_id']}")
                    print(f"  Title: {record2['title']}")

    finally:
        await driver.close()
        print("\nDatabase connection closed")


if __name__ == "__main__":
    asyncio.run(create_capsule())
