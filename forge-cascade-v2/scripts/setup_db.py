#!/usr/bin/env python3
"""
Forge Cascade V2 - Database Setup Script

This script initializes the Neo4j database schema, including:
- Node constraints (uniqueness)
- Indexes for performance
- Vector indexes for embeddings (if supported)
"""

import asyncio
import sys

# Add parent directory to path
sys.path.insert(0, str(__file__).rsplit('/', 2)[0])

from forge.config import get_settings
from forge.database.client import Neo4jClient


# Schema constraints
CONSTRAINTS = [
    # User constraints
    ("user_id_unique", "User", "id"),
    ("user_username_unique", "User", "username"),
    ("user_email_unique", "User", "email"),
    
    # Capsule constraints
    ("capsule_id_unique", "Capsule", "id"),
    
    # Proposal constraints
    ("proposal_id_unique", "Proposal", "id"),
    
    # Vote constraints
    ("vote_id_unique", "Vote", "id"),
    
    # Overlay constraints
    ("overlay_id_unique", "Overlay", "id"),
    ("overlay_name_unique", "Overlay", "name"),
    
    # Event constraints
    ("event_id_unique", "Event", "id"),
    
    # AuditLog constraints
    ("audit_id_unique", "AuditLog", "id"),
]

# Indexes for query performance
INDEXES = [
    # User indexes
    ("user_trust_level", "User", "trust_level"),
    ("user_is_active", "User", "is_active"),
    ("user_created_at", "User", "created_at"),
    
    # Capsule indexes
    ("capsule_domain", "Capsule", "domain"),
    ("capsule_visibility", "Capsule", "visibility"),
    ("capsule_created_at", "Capsule", "created_at"),
    ("capsule_created_by", "Capsule", "created_by"),
    
    # Proposal indexes
    ("proposal_status", "Proposal", "status"),
    ("proposal_type", "Proposal", "proposal_type"),
    ("proposal_created_at", "Proposal", "created_at"),
    ("proposal_expires_at", "Proposal", "expires_at"),
    
    # Event indexes
    ("event_type", "Event", "event_type"),
    ("event_timestamp", "Event", "timestamp"),
    
    # Audit indexes
    ("audit_action", "AuditLog", "action"),
    ("audit_timestamp", "AuditLog", "timestamp"),
    ("audit_user_id", "AuditLog", "user_id"),
    
    # Overlay indexes
    ("overlay_type", "Overlay", "overlay_type"),
    ("overlay_is_active", "Overlay", "is_active"),
]


async def create_constraints(client: Neo4jClient):
    """Create uniqueness constraints."""
    print("\nCreating constraints...")
    
    for name, label, property_name in CONSTRAINTS:
        try:
            query = f"""
            CREATE CONSTRAINT {name} IF NOT EXISTS
            FOR (n:{label})
            REQUIRE n.{property_name} IS UNIQUE
            """
            await client.execute_query(query)
            print(f"  ✓ {name}")
        except Exception as e:
            print(f"  ✗ {name}: {e}")


async def create_indexes(client: Neo4jClient):
    """Create performance indexes."""
    print("\nCreating indexes...")
    
    for name, label, property_name in INDEXES:
        try:
            query = f"""
            CREATE INDEX {name} IF NOT EXISTS
            FOR (n:{label})
            ON (n.{property_name})
            """
            await client.execute_query(query)
            print(f"  ✓ {name}")
        except Exception as e:
            print(f"  ✗ {name}: {e}")


async def create_vector_index(client: Neo4jClient):
    """Create vector index for embeddings (Neo4j 5.11+)."""
    print("\nCreating vector index...")
    
    try:
        # Check Neo4j version first
        result = await client.execute_query("CALL dbms.components() YIELD versions RETURN versions[0] as version")
        if result:
            version = result[0]["version"]
            print(f"  Neo4j version: {version}")
            
            # Vector indexes require Neo4j 5.11+
            major, minor = map(int, version.split('.')[:2])
            if major >= 5 and minor >= 11:
                query = """
                CREATE VECTOR INDEX capsule_embeddings IF NOT EXISTS
                FOR (c:Capsule)
                ON c.embedding
                OPTIONS {indexConfig: {
                    `vector.dimensions`: 1536,
                    `vector.similarity_function`: 'cosine'
                }}
                """
                await client.execute_query(query)
                print("  ✓ Vector index created")
            else:
                print("  ⚠ Vector indexes require Neo4j 5.11+")
    except Exception as e:
        print(f"  ⚠ Could not create vector index: {e}")


async def create_fulltext_index(client: Neo4jClient):
    """Create full-text search index for capsule content."""
    print("\nCreating full-text search index...")
    
    try:
        query = """
        CREATE FULLTEXT INDEX capsule_content_search IF NOT EXISTS
        FOR (c:Capsule)
        ON EACH [c.title, c.content]
        """
        await client.execute_query(query)
        print("  ✓ Full-text index created")
    except Exception as e:
        print(f"  ⚠ Could not create full-text index: {e}")


async def verify_schema(client: Neo4jClient):
    """Verify the schema was created correctly."""
    print("\nVerifying schema...")
    
    # Count constraints
    result = await client.execute_query("SHOW CONSTRAINTS")
    constraint_count = len(result) if result else 0
    print(f"  Constraints: {constraint_count}")
    
    # Count indexes
    result = await client.execute_query("SHOW INDEXES")
    index_count = len(result) if result else 0
    print(f"  Indexes: {index_count}")


async def main():
    """Run the setup script."""
    print("=" * 60)
    print("Forge Cascade V2 - Database Setup Script")
    print("=" * 60)
    
    settings = get_settings()
    
    print(f"\nConnecting to Neo4j: {settings.neo4j_uri}")
    
    client = Neo4jClient(
        uri=settings.neo4j_uri,
        user=settings.neo4j_user,
        password=settings.neo4j_password,
        database=settings.neo4j_database,
    )
    
    try:
        await client.connect()
        print("Connected successfully!")
        
        await create_constraints(client)
        await create_indexes(client)
        await create_vector_index(client)
        await create_fulltext_index(client)
        await verify_schema(client)
        
        print("\n" + "=" * 60)
        print("Database setup complete!")
        print("=" * 60)
        print("\nNext steps:")
        print("  1. Run 'python scripts/seed_data.py' to populate test data")
        print("  2. Start the API with 'uvicorn forge.api.app:create_app --factory'")
        
    except Exception as e:
        print(f"\nError: {e}")
        raise
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
