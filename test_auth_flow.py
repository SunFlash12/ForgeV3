"""Test the authentication flow directly."""
import asyncio
import os
import sys

# Set up environment variables before importing
os.environ.setdefault("EMBEDDING_PROVIDER", "mock")
os.environ.setdefault("LLM_PROVIDER", "mock")

sys.path.insert(0, 'C:\\Users\\idean\\Downloads\\Forge V3\\forge-cascade-v2')

from forge.config import get_settings
from forge.database.client import Neo4jClient
from forge.repositories.user_repository import UserRepository
from forge.security.tokens import verify_token

# The user ID from the token
USER_ID = "ba21f02f-81b4-4478-a60b-13054b25d181"

async def test():
    settings = get_settings()
    print(f"Settings loaded: JWT secret = {settings.jwt_secret_key[:20]}...")

    # Test database connection
    print("\nConnecting to Neo4j...")
    client = Neo4jClient(
        uri=settings.neo4j_uri,
        username=settings.neo4j_username,
        password=settings.neo4j_password,
        database=settings.neo4j_database,
    )
    await client.connect()
    print("Connected to Neo4j")

    # Test user lookup
    print(f"\nLooking up user by ID: {USER_ID}")
    repo = UserRepository(client)

    # Try direct query first
    query = """
        MATCH (u:User {id: $id})
        RETURN u {.*} AS user
    """
    result = await client.execute_single(query, {"id": USER_ID})
    print(f"Direct query result: {result}")

    # Now try through repository
    user = await repo.get_by_id(USER_ID)
    print(f"Repository get_by_id result: {user}")

    await client.close()
    print("\nDone")

if __name__ == "__main__":
    asyncio.run(test())
