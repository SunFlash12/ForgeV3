"""
Integration Test: Database Connection

Verifies that the system can actually connect to Neo4j and perform operations.
These tests FAIL if the database is unavailable - that's the point.
"""

import pytest

pytestmark = pytest.mark.asyncio


class TestDatabaseConnection:
    """Verify real Neo4j connectivity."""

    async def test_database_connects(self, real_db_client):
        """Database client should connect to real Neo4j."""
        # If we get here, connection already succeeded in fixture
        assert real_db_client is not None

    async def test_health_check_passes(self, real_db_client):
        """Health check should pass with real database."""
        is_healthy = await real_db_client.health_check()
        assert is_healthy is True, "Database health check must pass"

    async def test_can_execute_query(self, real_db_client):
        """Should be able to execute a simple Cypher query."""
        result = await real_db_client.execute(
            "RETURN 1 as value",
            {},
        )
        assert len(result) == 1
        assert result[0]["value"] == 1

    async def test_can_create_and_read_node(self, integration_db):
        """Should be able to create and read a node."""
        import uuid

        test_id = str(uuid.uuid4())

        # Create
        await integration_db.execute(
            """
            CREATE (n:IntegrationTest {id: $id, name: $name, test_prefix: $prefix})
            RETURN n.id as id
            """,
            {"id": test_id, "name": "test_node", "prefix": "integration_test"},
        )

        # Read
        result = await integration_db.execute(
            "MATCH (n:IntegrationTest {id: $id}) RETURN n.name as name",
            {"id": test_id},
        )

        assert len(result) == 1
        assert result[0]["name"] == "test_node"

        # Cleanup
        await integration_db.execute(
            "MATCH (n:IntegrationTest {id: $id}) DELETE n",
            {"id": test_id},
        )


class TestUserRepository:
    """Verify user repository works with real database."""

    async def test_create_user(self, integration_db):
        """Should create a real user in the database."""
        from uuid import uuid4

        from forge.repositories.user_repository import UserRepository

        repo = UserRepository(integration_db)
        user_id = str(uuid4())
        username = f"inttest_{uuid4().hex[:8]}"

        try:
            user = await repo.create(
                user_id=user_id,
                username=username,
                email=f"{username}@test.local",
                password_hash="$argon2id$v=19$m=65536,t=3,p=4$test",
                trust_flame=60,
            )

            assert user is not None
            assert user.get("id") == user_id or user.get("user_id") == user_id
            assert user.get("username") == username

        finally:
            # Cleanup
            await repo.delete(user_id)

    async def test_user_lookup(self, integration_db):
        """Should find user by username."""
        from uuid import uuid4

        from forge.repositories.user_repository import UserRepository

        repo = UserRepository(integration_db)
        user_id = str(uuid4())
        username = f"lookup_{uuid4().hex[:8]}"

        try:
            # Create
            await repo.create(
                user_id=user_id,
                username=username,
                email=f"{username}@test.local",
                password_hash="$argon2id$v=19$m=65536,t=3,p=4$test",
                trust_flame=60,
            )

            # Lookup
            found = await repo.get_by_username(username)
            assert found is not None
            assert found.get("username") == username

        finally:
            await repo.delete(user_id)


class TestCapsuleRepository:
    """Verify capsule repository works with real database."""

    async def test_create_capsule(self, integration_db):
        """Should create a real capsule in the database."""
        from uuid import uuid4

        from forge.repositories.capsule_repository import CapsuleRepository

        repo = CapsuleRepository(integration_db)
        capsule_id = str(uuid4())
        owner_id = str(uuid4())

        try:
            capsule = await repo.create(
                capsule_id=capsule_id,
                title="Integration Test Capsule",
                content="This capsule was created by an integration test.",
                owner_id=owner_id,
                capsule_type="knowledge",
                trust_level=60,
            )

            assert capsule is not None

            # Verify we can read it back
            found = await repo.get_by_id(capsule_id)
            assert found is not None
            assert found.get("title") == "Integration Test Capsule"

        finally:
            # Cleanup
            await repo.delete(capsule_id)
