#!/usr/bin/env python3
"""
Forge Cascade V2 - Seed Data Script

This script populates the Neo4j database with initial data for development
and testing purposes. It creates:
- Admin and test users
- Sample knowledge capsules with lineage
- Sample proposals and votes
- Default overlay configurations

SECURITY: Passwords are read from environment variables. If not set,
secure random passwords are generated and saved to .seed_credentials
(which is gitignored).
"""

import asyncio
import secrets
import string
import sys
from datetime import datetime, timedelta
from uuid import uuid4

# Add parent directory to path
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from forge.config import get_settings
from forge.database.client import Neo4jClient
from forge.security.password import hash_password
from forge.models.user import TrustLevel


def generate_secure_password(length: int = 24) -> str:
    """Generate a cryptographically secure password."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    while True:
        password = ''.join(secrets.choice(alphabet) for _ in range(length))
        # Ensure password has at least one of each type
        if (any(c.islower() for c in password) and
            any(c.isupper() for c in password) and
            any(c.isdigit() for c in password) and
            any(c in '!@#$%^&*' for c in password)):
            return password


def get_seed_password(username: str) -> str:
    """Get password from environment variable or generate one."""
    env_var = f"SEED_{username.upper()}_PASSWORD"
    password = os.environ.get(env_var)
    if password:
        return password
    # Generate and return a secure password
    return generate_secure_password()


def save_credentials(credentials: dict[str, str], filepath: str) -> None:
    """Save generated credentials to a local file (gitignored)."""
    with open(filepath, 'w') as f:
        f.write("# Forge Seed User Credentials\n")
        f.write("# SECURITY: Do not commit this file!\n")
        f.write("# Add these to your .env file:\n\n")
        for username, password in credentials.items():
            f.write(f"SEED_{username.upper()}_PASSWORD={password}\n")
        f.write("\n# Or use directly:\n")
        for username, password in credentials.items():
            f.write(f"# {username}: {password}\n")


async def seed_users(client: Neo4jClient) -> dict[str, str]:
    """Create seed users and return their IDs."""
    print("Creating users...")

    users = {}
    generated_credentials = {}

    # User configuration - passwords come from environment variables
    user_configs = [
        {
            "username": "admin",
            "email": "admin@forge.example.com",
            "display_name": "System Administrator",
            "trust_level": TrustLevel.CORE,
            "role": "admin",  # Admin role for administrative access
        },
        {
            "username": "oracle",
            "email": "oracle@forge.example.com",
            "display_name": "Oracle (Ghost Council)",
            "trust_level": TrustLevel.TRUSTED,
            "role": "user",
        },
        {
            "username": "developer",
            "email": "dev@forge.example.com",
            "display_name": "Test Developer",
            "trust_level": TrustLevel.STANDARD,
            "role": "user",
        },
        {
            "username": "analyst",
            "email": "analyst@forge.example.com",
            "display_name": "Data Analyst",
            "trust_level": TrustLevel.SANDBOX,
            "role": "user",
        },
    ]

    # Build user_data with passwords from environment
    user_data = []
    for config in user_configs:
        password = get_seed_password(config["username"])
        generated_credentials[config["username"]] = password
        user_data.append({**config, "password": password})
    
    for user in user_data:
        user_id = str(uuid4())
        password_hash = hash_password(user["password"])
        
        query = """
        MERGE (u:User {username: $username})
        ON CREATE SET
            u.id = $id,
            u.email = $email,
            u.password_hash = $password_hash,
            u.display_name = $display_name,
            u.trust_flame = $trust_flame,
            u.role = $role,
            u.is_active = true,
            u.created_at = datetime(),
            u.updated_at = datetime()
        ON MATCH SET
            u.trust_flame = $trust_flame,
            u.display_name = $display_name,
            u.role = $role,
            u.updated_at = datetime()
        RETURN u.id as id
        """

        result = await client.execute(
            query,
            {
                "id": user_id,
                "username": user["username"],
                "email": user["email"],
                "password_hash": password_hash,
                "display_name": user["display_name"],
                "trust_flame": user["trust_level"].value,
                "role": user.get("role", "user"),
            }
        )
        
        users[user["username"]] = user_id
        print(f"  Created user: {user['username']} ({user['trust_level'].value})")

    # Save credentials to file for reference (gitignored)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    creds_file = os.path.join(script_dir, ".seed_credentials")
    save_credentials(generated_credentials, creds_file)

    return users, generated_credentials


async def seed_capsules(client: Neo4jClient, users: dict[str, str]) -> list[str]:
    """Create sample knowledge capsules with lineage."""
    print("\nCreating knowledge capsules...")
    
    admin_id = users["admin"]
    dev_id = users["developer"]
    
    capsules = []
    
    # Root capsule
    root_id = str(uuid4())
    await client.execute(
        """
        CREATE (c:Capsule {
            id: $id,
            title: 'Forge System Architecture',
            content: 'Forge is an institutional memory engine designed to preserve and evolve organizational knowledge through a layered overlay system.',
            type: 'KNOWLEDGE',
            version: '1.0.0',
            owner_id: $user_id,
            trust_level: 60,
            is_archived: false,
            view_count: 0,
            fork_count: 0,
            tags: ['architecture', 'core'],
            metadata: '{}',
            created_at: datetime(),
            updated_at: datetime()
        })
        WITH c
        MATCH (u:User {id: $user_id})
        CREATE (u)-[:CREATED]->(c)
        RETURN c.id
        """,
        {"id": root_id, "user_id": admin_id}
    )
    capsules.append(root_id)
    print(f"  Created root capsule: Forge System Architecture")
    
    # Child capsules
    child_capsules = [
        {
            "title": "Security Layer Design",
            "content": "The security layer implements trust-based access control with five levels: UNTRUSTED, SANDBOX, STANDARD, TRUSTED, and CORE.",
            "type": "KNOWLEDGE",
            "tags": ["security", "architecture"],
        },
        {
            "title": "Overlay System",
            "content": "Overlays are modular processing units that observe and transform knowledge as it flows through the system.",
            "type": "KNOWLEDGE",
            "tags": ["overlays", "architecture"],
        },
        {
            "title": "Ghost Council Governance",
            "content": "The Ghost Council is an AI-powered governance mechanism that provides wisdom and guidance on system decisions.",
            "type": "PRINCIPLE",
            "tags": ["governance", "ghost-council"],
        },
    ]
    
    for cap in child_capsules:
        cap_id = str(uuid4())
        await client.execute(
            """
            CREATE (c:Capsule {
                id: $id,
                title: $title,
                content: $content,
                type: $type,
                version: '1.0.0',
                owner_id: $user_id,
                parent_id: $parent_id,
                trust_level: 60,
                is_archived: false,
                view_count: 0,
                fork_count: 0,
                tags: $tags,
                metadata: '{}',
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
            {
                "id": cap_id,
                "title": cap["title"],
                "content": cap["content"],
                "type": cap["type"],
                "tags": cap["tags"],
                "user_id": dev_id,
                "parent_id": root_id,
            }
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
            "status": "voting",
            "creator": "developer",
        },
        {
            "title": "Increase Trust Score Threshold for TRUSTED Level",
            "description": "Raise the minimum trust score for TRUSTED level from 60 to 75 to ensure higher quality contributions.",
            "status": "draft",
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
        
        await client.execute(
            """
            CREATE (p:Proposal {
                id: $id,
                title: $title,
                description: $description,
                status: $status,
                type: 'policy',
                proposer_id: $user_id,
                voting_period_days: 7,
                quorum_percent: 0.1,
                pass_threshold: 0.5,
                votes_for: 0,
                votes_against: 0,
                votes_abstain: 0,
                weight_for: 0.0,
                weight_against: 0.0,
                weight_abstain: 0.0,
                action: '{}',
                created_at: datetime(),
                updated_at: datetime()
            })
            WITH p
            MATCH (u:User {id: $user_id})
            CREATE (u)-[:PROPOSED]->(p)
            RETURN p.id
            """,
            {
                "id": prop_id,
                "title": prop["title"],
                "description": prop["description"],
                "status": prop["status"],
                "user_id": user_id,
            }
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
        
        await client.execute(
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
            {
                "id": overlay_id,
                "name": overlay["name"],
                "display_name": overlay["display_name"],
                "overlay_type": overlay["overlay_type"],
                "description": overlay["description"],
                "is_active": overlay["is_active"],
                "priority": overlay["priority"],
            }
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
        result = await client.execute("MATCH (u:User) RETURN count(u) as count", {})
        if result and result[0]["count"] > 0:
            print("Database already contains data.")
            # SECURITY FIX (Audit 4): Require confirmation before deleting all data
            confirm = input("This will DELETE ALL DATA in the database. Continue? (yes/no): ")
            if confirm.lower() != "yes":
                print("Aborted. No changes made.")
                return
            print("Clearing database and reseeding...")
            await client.execute("MATCH (n) DETACH DELETE n", {})
        
        # Seed data
        users, credentials = await seed_users(client)
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

        # Show credential info
        script_dir = os.path.dirname(os.path.abspath(__file__))
        creds_file = os.path.join(script_dir, ".seed_credentials")
        print(f"\nCredentials saved to: {creds_file}")
        print("Add the environment variables from that file to your .env")
        print("\nUsers created:")
        print("  admin (CORE)")
        print("  oracle (TRUSTED)")
        print("  developer (STANDARD)")
        print("  analyst (SANDBOX)")
        
    except Exception as e:
        print(f"\nError: {e}")
        raise
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
