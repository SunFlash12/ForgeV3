#!/usr/bin/env python3
"""
Forge Cascade V2 - Seed Data Script

This script populates the Neo4j database with initial data for development
and testing purposes. It creates:
- Admin and test users
- Sample knowledge capsules with lineage
- Sample proposals and votes
- Default overlay configurations
"""

import asyncio
import sys
from datetime import datetime, timedelta
from uuid import uuid4

# Add parent directory to path
sys.path.insert(0, str(__file__).rsplit('/', 2)[0])

from forge.config import get_settings
from forge.database.client import Neo4jClient
from forge.security.password import hash_password
from forge.models.user import TrustLevel


async def seed_users(client: Neo4jClient) -> dict[str, str]:
    """Create seed users and return their IDs."""
    print("Creating users...")
    
    users = {}
    
    user_data = [
        {
            "username": "admin",
            "email": "admin@forge.local",
            "password": "AdminPass123!",
            "display_name": "System Administrator",
            "trust_level": TrustLevel.CORE,
        },
        {
            "username": "oracle",
            "email": "oracle@forge.local", 
            "password": "OraclePass123!",
            "display_name": "Oracle (Ghost Council)",
            "trust_level": TrustLevel.TRUSTED,
        },
        {
            "username": "developer",
            "email": "dev@forge.local",
            "password": "DevPass123!",
            "display_name": "Test Developer",
            "trust_level": TrustLevel.STANDARD,
        },
        {
            "username": "analyst",
            "email": "analyst@forge.local",
            "password": "AnalystPass123!",
            "display_name": "Data Analyst",
            "trust_level": TrustLevel.SANDBOX,
        },
    ]
    
    for user in user_data:
        user_id = str(uuid4())
        password_hash = hash_password(user["password"])
        
        query = """
        CREATE (u:User {
            id: $id,
            username: $username,
            email: $email,
            password_hash: $password_hash,
            display_name: $display_name,
            trust_level: $trust_level,
            trust_score: $trust_score,
            is_active: true,
            created_at: datetime(),
            updated_at: datetime()
        })
        RETURN u.id as id
        """
        
        result = await client.execute_query(
            query,
            id=user_id,
            username=user["username"],
            email=user["email"],
            password_hash=password_hash,
            display_name=user["display_name"],
            trust_level=user["trust_level"].value,
            trust_score=user["trust_level"].value * 20 + 10,
        )
        
        users[user["username"]] = user_id
        print(f"  Created user: {user['username']} ({user['trust_level'].value})")
    
    return users


async def seed_capsules(client: Neo4jClient, users: dict[str, str]) -> list[str]:
    """Create sample knowledge capsules with lineage."""
    print("\nCreating knowledge capsules...")
    
    admin_id = users["admin"]
    dev_id = users["developer"]
    
    capsules = []
    
    # Root capsule
    root_id = str(uuid4())
    await client.execute_query(
        """
        CREATE (c:Capsule {
            id: $id,
            title: 'Forge System Architecture',
            content: 'Forge is an institutional memory engine designed to preserve and evolve organizational knowledge through a layered overlay system.',
            content_type: 'markdown',
            domain: 'architecture',
            visibility: 'public',
            version: 1,
            created_by: $user_id,
            created_at: datetime(),
            updated_at: datetime()
        })
        WITH c
        MATCH (u:User {id: $user_id})
        CREATE (u)-[:CREATED]->(c)
        RETURN c.id
        """,
        id=root_id,
        user_id=admin_id,
    )
    capsules.append(root_id)
    print(f"  Created root capsule: Forge System Architecture")
    
    # Child capsules
    child_capsules = [
        {
            "title": "Security Layer Design",
            "content": "The security layer implements trust-based access control with five levels: UNTRUSTED, SANDBOX, STANDARD, TRUSTED, and CORE.",
            "domain": "security",
        },
        {
            "title": "Overlay System",
            "content": "Overlays are modular processing units that observe and transform knowledge as it flows through the system.",
            "domain": "architecture",
        },
        {
            "title": "Ghost Council Governance",
            "content": "The Ghost Council is an AI-powered governance mechanism that provides wisdom and guidance on system decisions.",
            "domain": "governance",
        },
    ]
    
    for cap in child_capsules:
        cap_id = str(uuid4())
        await client.execute_query(
            """
            CREATE (c:Capsule {
                id: $id,
                title: $title,
                content: $content,
                content_type: 'markdown',
                domain: $domain,
                visibility: 'public',
                version: 1,
                created_by: $user_id,
                created_at: datetime(),
                updated_at: datetime()
            })
            WITH c
            MATCH (u:User {id: $user_id})
            CREATE (u)-[:CREATED]->(c)
            WITH c
            MATCH (parent:Capsule {id: $parent_id})
            CREATE (c)-[:DERIVED_FROM {
                relationship_type: 'extends',
                created_at: datetime()
            }]->(parent)
            RETURN c.id
            """,
            id=cap_id,
            title=cap["title"],
            content=cap["content"],
            domain=cap["domain"],
            user_id=dev_id,
            parent_id=root_id,
        )
        capsules.append(cap_id)
        print(f"  Created child capsule: {cap['title']}")
    
    return capsules


async def seed_proposals(client: Neo4jClient, users: dict[str, str]) -> list[str]:
    """Create sample governance proposals."""
    print("\nCreating governance proposals...")
    
    proposals = []
    
    proposal_data = [
        {
            "title": "Enable ML Intelligence Overlay by Default",
            "description": "Proposal to activate the ML Intelligence overlay for all new capsules to enable automatic pattern recognition.",
            "status": "active",
            "creator": "developer",
        },
        {
            "title": "Increase Trust Score Threshold for TRUSTED Level",
            "description": "Raise the minimum trust score for TRUSTED level from 60 to 75 to ensure higher quality contributions.",
            "status": "pending",
            "creator": "admin",
        },
        {
            "title": "Add Email Notifications for Proposals",
            "description": "Implement email notifications when new proposals are created or when votes are cast.",
            "status": "passed",
            "creator": "oracle",
        },
    ]
    
    for prop in proposal_data:
        prop_id = str(uuid4())
        user_id = users[prop["creator"]]
        
        await client.execute_query(
            """
            CREATE (p:Proposal {
                id: $id,
                title: $title,
                description: $description,
                status: $status,
                proposal_type: 'policy',
                quorum_threshold: 0.5,
                approval_threshold: 0.6,
                created_by: $user_id,
                created_at: datetime(),
                expires_at: datetime() + duration('P7D')
            })
            WITH p
            MATCH (u:User {id: $user_id})
            CREATE (u)-[:PROPOSED]->(p)
            RETURN p.id
            """,
            id=prop_id,
            title=prop["title"],
            description=prop["description"],
            status=prop["status"],
            user_id=user_id,
        )
        proposals.append(prop_id)
        print(f"  Created proposal: {prop['title']}")
    
    return proposals


async def seed_overlays(client: Neo4jClient) -> list[str]:
    """Create overlay configurations."""
    print("\nCreating overlay configurations...")
    
    overlays = []
    
    overlay_data = [
        {
            "name": "security_validator",
            "display_name": "Security Validator",
            "overlay_type": "security",
            "description": "Validates content for security threats and policy compliance",
            "is_active": True,
            "priority": 1,
        },
        {
            "name": "ml_intelligence",
            "display_name": "ML Intelligence",
            "overlay_type": "ml",
            "description": "Pattern recognition and content classification using machine learning",
            "is_active": True,
            "priority": 2,
        },
        {
            "name": "governance",
            "display_name": "Governance Engine",
            "overlay_type": "governance",
            "description": "Manages proposals, voting, and policy enforcement",
            "is_active": True,
            "priority": 3,
        },
        {
            "name": "lineage_tracker",
            "display_name": "Lineage Tracker",
            "overlay_type": "lineage",
            "description": "Tracks knowledge ancestry and evolution",
            "is_active": True,
            "priority": 4,
        },
    ]
    
    for overlay in overlay_data:
        overlay_id = str(uuid4())
        
        await client.execute_query(
            """
            CREATE (o:Overlay {
                id: $id,
                name: $name,
                display_name: $display_name,
                overlay_type: $overlay_type,
                description: $description,
                is_active: $is_active,
                priority: $priority,
                config: '{}',
                created_at: datetime(),
                updated_at: datetime()
            })
            RETURN o.id
            """,
            id=overlay_id,
            name=overlay["name"],
            display_name=overlay["display_name"],
            overlay_type=overlay["overlay_type"],
            description=overlay["description"],
            is_active=overlay["is_active"],
            priority=overlay["priority"],
        )
        overlays.append(overlay_id)
        print(f"  Created overlay: {overlay['display_name']}")
    
    return overlays


async def main():
    """Run the seed script."""
    print("=" * 60)
    print("Forge Cascade V2 - Database Seed Script")
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
        print("Connected successfully!\n")
        
        # Check if data already exists
        result = await client.execute_query("MATCH (u:User) RETURN count(u) as count")
        if result and result[0]["count"] > 0:
            response = input("Database already contains data. Clear and reseed? [y/N]: ")
            if response.lower() != 'y':
                print("Aborting.")
                return
            
            print("Clearing existing data...")
            await client.execute_query("MATCH (n) DETACH DELETE n")
        
        # Seed data
        users = await seed_users(client)
        capsules = await seed_capsules(client, users)
        proposals = await seed_proposals(client, users)
        overlays = await seed_overlays(client)
        
        print("\n" + "=" * 60)
        print("Seed Complete!")
        print("=" * 60)
        print(f"  Users: {len(users)}")
        print(f"  Capsules: {len(capsules)}")
        print(f"  Proposals: {len(proposals)}")
        print(f"  Overlays: {len(overlays)}")
        print("\nDefault Credentials:")
        print("  admin / AdminPass123!")
        print("  developer / DevPass123!")
        print("  analyst / AnalystPass123!")
        
    except Exception as e:
        print(f"\nError: {e}")
        raise
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
