"""
Neo4j Schema Manager

Manages database schema including constraints, indexes, and vector indexes
for semantic search. Based on V2 specification requirements.
"""

import re
from typing import Any

import structlog
from neo4j.exceptions import (
    ClientError,
    ConstraintError,
    DatabaseError,
    ServiceUnavailable,
)

from forge.config import settings
from forge.database.client import Neo4jClient

logger = structlog.get_logger(__name__)


# SECURITY FIX (Audit 2): Validate identifiers before using in schema operations
# Neo4j identifiers must be alphanumeric with underscores only
_SAFE_IDENTIFIER_PATTERN = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')


def _validate_identifier(name: str) -> bool:
    """
    Validate that an identifier (constraint/index name) is safe for use in queries.

    Returns True if safe, False otherwise.
    """
    if not name or len(name) > 128:
        return False
    return bool(_SAFE_IDENTIFIER_PATTERN.match(name))


class SchemaManager:
    """
    Manages Neo4j schema setup and migrations.

    Creates all necessary constraints, indexes, and vector indexes
    for the Forge system.

    NOTE: Schema Migration Atomicity Limitations
    =============================================
    Neo4j schema operations (CREATE CONSTRAINT, CREATE INDEX) are DDL operations
    that cannot be wrapped in transactions with DML operations. This means:

    1. Each constraint/index is created in its own implicit transaction
    2. If one fails, others may have succeeded - partial application is possible
    3. Full rollback of schema changes is not supported by Neo4j

    Mitigation Strategies Implemented:
    - All operations use IF NOT EXISTS for idempotency
    - Running setup_all() again will skip existing and retry failed operations
    - Results dict tracks success/failure for each operation
    - Operations are logged for audit purposes

    Future Improvement Recommendations:
    - Implement a migrations table to track applied migrations by version
    - Add pre-flight validation before applying schema changes
    - Create backup procedures before major schema updates
    - Consider Neo4j schema evolution patterns for breaking changes
    """

    def __init__(self, client: Neo4jClient):
        self.client = client

    async def setup_all(self) -> dict[str, bool]:
        """
        Set up all schema elements.

        Returns:
            Dict of schema element names to success status
        """
        results = {}

        # Create constraints
        constraint_results = await self.create_constraints()
        results.update(constraint_results)

        # Create indexes
        index_results = await self.create_indexes()
        results.update(index_results)

        # Create vector indexes
        vector_results = await self.create_vector_indexes()
        results.update(vector_results)

        logger.info(
            "Schema setup complete",
            total=len(results),
            successful=sum(1 for v in results.values() if v),
            failed=sum(1 for v in results.values() if not v),
        )

        return results

    async def create_constraints(self) -> dict[str, bool]:
        """Create uniqueness and existence constraints."""

        constraints = [
            # Capsule constraints
            (
                "capsule_id_unique",
                "CREATE CONSTRAINT capsule_id_unique IF NOT EXISTS "
                "FOR (c:Capsule) REQUIRE c.id IS UNIQUE"
            ),

            # User constraints
            (
                "user_id_unique",
                "CREATE CONSTRAINT user_id_unique IF NOT EXISTS "
                "FOR (u:User) REQUIRE u.id IS UNIQUE"
            ),
            (
                "user_username_unique",
                "CREATE CONSTRAINT user_username_unique IF NOT EXISTS "
                "FOR (u:User) REQUIRE u.username IS UNIQUE"
            ),
            (
                "user_email_unique",
                "CREATE CONSTRAINT user_email_unique IF NOT EXISTS "
                "FOR (u:User) REQUIRE u.email IS UNIQUE"
            ),

            # Overlay constraints
            (
                "overlay_id_unique",
                "CREATE CONSTRAINT overlay_id_unique IF NOT EXISTS "
                "FOR (o:Overlay) REQUIRE o.id IS UNIQUE"
            ),
            (
                "overlay_name_unique",
                "CREATE CONSTRAINT overlay_name_unique IF NOT EXISTS "
                "FOR (o:Overlay) REQUIRE o.name IS UNIQUE"
            ),

            # Proposal constraints
            (
                "proposal_id_unique",
                "CREATE CONSTRAINT proposal_id_unique IF NOT EXISTS "
                "FOR (p:Proposal) REQUIRE p.id IS UNIQUE"
            ),

            # Vote constraints
            (
                "vote_id_unique",
                "CREATE CONSTRAINT vote_id_unique IF NOT EXISTS "
                "FOR (v:Vote) REQUIRE v.id IS UNIQUE"
            ),

            # AuditLog constraints
            (
                "auditlog_id_unique",
                "CREATE CONSTRAINT auditlog_id_unique IF NOT EXISTS "
                "FOR (a:AuditLog) REQUIRE a.id IS UNIQUE"
            ),

            # Event constraints
            (
                "event_id_unique",
                "CREATE CONSTRAINT event_id_unique IF NOT EXISTS "
                "FOR (e:Event) REQUIRE e.id IS UNIQUE"
            ),

            # ═══════════════════════════════════════════════════════════════
            # GRAPH EXTENSIONS: Temporal & Semantic
            # ═══════════════════════════════════════════════════════════════

            # CapsuleVersion constraints
            (
                "capsuleversion_id_unique",
                "CREATE CONSTRAINT capsuleversion_id_unique IF NOT EXISTS "
                "FOR (v:CapsuleVersion) REQUIRE v.id IS UNIQUE"
            ),

            # TrustSnapshot constraints
            (
                "trustsnapshot_id_unique",
                "CREATE CONSTRAINT trustsnapshot_id_unique IF NOT EXISTS "
                "FOR (t:TrustSnapshot) REQUIRE t.id IS UNIQUE"
            ),

            # GraphSnapshot constraints
            (
                "graphsnapshot_id_unique",
                "CREATE CONSTRAINT graphsnapshot_id_unique IF NOT EXISTS "
                "FOR (g:GraphSnapshot) REQUIRE g.id IS UNIQUE"
            ),

            # SemanticEdge constraints
            (
                "semanticedge_id_unique",
                "CREATE CONSTRAINT semanticedge_id_unique IF NOT EXISTS "
                "FOR (s:SemanticEdge) REQUIRE s.id IS UNIQUE"
            ),

            # ═══════════════════════════════════════════════════════════════
            # CHAT ROOM ACCESS CONTROL (Audit 6 - Session 4)
            # ═══════════════════════════════════════════════════════════════

            # ChatRoom constraints
            (
                "chatroom_id_unique",
                "CREATE CONSTRAINT chatroom_id_unique IF NOT EXISTS "
                "FOR (r:ChatRoom) REQUIRE r.id IS UNIQUE"
            ),
            (
                "chatroom_invite_code_unique",
                "CREATE CONSTRAINT chatroom_invite_code_unique IF NOT EXISTS "
                "FOR (r:ChatRoom) REQUIRE r.invite_code IS UNIQUE"
            ),

            # ChatMessage constraints
            (
                "chatmessage_id_unique",
                "CREATE CONSTRAINT chatmessage_id_unique IF NOT EXISTS "
                "FOR (m:ChatMessage) REQUIRE m.id IS UNIQUE"
            ),
        ]

        results = {}
        for name, query in constraints:
            try:
                await self.client.execute(query)
                results[name] = True
                logger.debug(f"Created constraint: {name}")
            except ConstraintError as e:
                # Constraint already exists or conflicts - expected in some cases
                results[name] = False
                logger.warning(f"Constraint conflict: {name}", error=str(e))
            except ClientError as e:
                # Syntax or client-side error - likely a bug in the query
                results[name] = False
                logger.error(f"Client error creating constraint: {name}", error=str(e))
            except DatabaseError as e:
                # Database-level error - may be transient
                results[name] = False
                logger.error(f"Database error creating constraint: {name}", error=str(e))
            except ServiceUnavailable as e:
                # Connection lost - re-raise as this is fatal
                logger.critical(f"Database unavailable while creating constraint: {name}", error=str(e))
                raise
            except Exception as e:
                # Unexpected error - log with full type info
                results[name] = False
                logger.error(
                    f"Unexpected error creating constraint: {name}",
                    error_type=type(e).__name__,
                    error=str(e)
                )

        return results

    async def create_indexes(self) -> dict[str, bool]:
        """Create regular indexes for common queries."""

        indexes = [
            # Capsule indexes
            (
                "capsule_type_idx",
                "CREATE INDEX capsule_type_idx IF NOT EXISTS "
                "FOR (c:Capsule) ON (c.type)"
            ),
            (
                "capsule_owner_idx",
                "CREATE INDEX capsule_owner_idx IF NOT EXISTS "
                "FOR (c:Capsule) ON (c.owner_id)"
            ),
            (
                "capsule_trust_idx",
                "CREATE INDEX capsule_trust_idx IF NOT EXISTS "
                "FOR (c:Capsule) ON (c.trust_level)"
            ),
            (
                "capsule_created_idx",
                "CREATE INDEX capsule_created_idx IF NOT EXISTS "
                "FOR (c:Capsule) ON (c.created_at)"
            ),

            # User indexes
            (
                "user_role_idx",
                "CREATE INDEX user_role_idx IF NOT EXISTS "
                "FOR (u:User) ON (u.role)"
            ),
            (
                "user_active_idx",
                "CREATE INDEX user_active_idx IF NOT EXISTS "
                "FOR (u:User) ON (u.is_active)"
            ),
            (
                "user_trust_idx",
                "CREATE INDEX user_trust_idx IF NOT EXISTS "
                "FOR (u:User) ON (u.trust_flame)"
            ),

            # Overlay indexes
            (
                "overlay_state_idx",
                "CREATE INDEX overlay_state_idx IF NOT EXISTS "
                "FOR (o:Overlay) ON (o.state)"
            ),
            (
                "overlay_trust_idx",
                "CREATE INDEX overlay_trust_idx IF NOT EXISTS "
                "FOR (o:Overlay) ON (o.trust_level)"
            ),

            # Proposal indexes
            (
                "proposal_status_idx",
                "CREATE INDEX proposal_status_idx IF NOT EXISTS "
                "FOR (p:Proposal) ON (p.status)"
            ),
            (
                "proposal_proposer_idx",
                "CREATE INDEX proposal_proposer_idx IF NOT EXISTS "
                "FOR (p:Proposal) ON (p.proposer_id)"
            ),

            # AuditLog indexes
            (
                "audit_entity_idx",
                "CREATE INDEX audit_entity_idx IF NOT EXISTS "
                "FOR (a:AuditLog) ON (a.entity_type, a.entity_id)"
            ),
            (
                "audit_user_idx",
                "CREATE INDEX audit_user_idx IF NOT EXISTS "
                "FOR (a:AuditLog) ON (a.user_id)"
            ),
            (
                "audit_timestamp_idx",
                "CREATE INDEX audit_timestamp_idx IF NOT EXISTS "
                "FOR (a:AuditLog) ON (a.timestamp)"
            ),
            (
                "audit_correlation_idx",
                "CREATE INDEX audit_correlation_idx IF NOT EXISTS "
                "FOR (a:AuditLog) ON (a.correlation_id)"
            ),

            # Event indexes
            (
                "event_type_idx",
                "CREATE INDEX event_type_idx IF NOT EXISTS "
                "FOR (e:Event) ON (e.type)"
            ),
            (
                "event_source_idx",
                "CREATE INDEX event_source_idx IF NOT EXISTS "
                "FOR (e:Event) ON (e.source)"
            ),
            (
                "event_timestamp_idx",
                "CREATE INDEX event_timestamp_idx IF NOT EXISTS "
                "FOR (e:Event) ON (e.timestamp)"
            ),

            # ═══════════════════════════════════════════════════════════════
            # GRAPH EXTENSIONS: Temporal Indexes
            # ═══════════════════════════════════════════════════════════════

            # CapsuleVersion indexes
            (
                "version_capsule_idx",
                "CREATE INDEX version_capsule_idx IF NOT EXISTS "
                "FOR (v:CapsuleVersion) ON (v.capsule_id)"
            ),
            (
                "version_timestamp_idx",
                "CREATE INDEX version_timestamp_idx IF NOT EXISTS "
                "FOR (v:CapsuleVersion) ON (v.created_at)"
            ),
            (
                "version_type_idx",
                "CREATE INDEX version_type_idx IF NOT EXISTS "
                "FOR (v:CapsuleVersion) ON (v.snapshot_type)"
            ),
            (
                "version_creator_idx",
                "CREATE INDEX version_creator_idx IF NOT EXISTS "
                "FOR (v:CapsuleVersion) ON (v.created_by)"
            ),

            # TrustSnapshot indexes
            (
                "trustsnapshot_entity_idx",
                "CREATE INDEX trustsnapshot_entity_idx IF NOT EXISTS "
                "FOR (t:TrustSnapshot) ON (t.entity_id, t.entity_type)"
            ),
            (
                "trustsnapshot_time_idx",
                "CREATE INDEX trustsnapshot_time_idx IF NOT EXISTS "
                "FOR (t:TrustSnapshot) ON (t.timestamp)"
            ),
            (
                "trustsnapshot_type_idx",
                "CREATE INDEX trustsnapshot_type_idx IF NOT EXISTS "
                "FOR (t:TrustSnapshot) ON (t.change_type)"
            ),

            # GraphSnapshot indexes
            (
                "graphsnapshot_time_idx",
                "CREATE INDEX graphsnapshot_time_idx IF NOT EXISTS "
                "FOR (g:GraphSnapshot) ON (g.created_at)"
            ),

            # ═══════════════════════════════════════════════════════════════
            # GRAPH EXTENSIONS: Semantic Edge Indexes
            # ═══════════════════════════════════════════════════════════════

            # SemanticEdge indexes (for edge node pattern)
            (
                "semanticedge_source_idx",
                "CREATE INDEX semanticedge_source_idx IF NOT EXISTS "
                "FOR (s:SemanticEdge) ON (s.source_id)"
            ),
            (
                "semanticedge_target_idx",
                "CREATE INDEX semanticedge_target_idx IF NOT EXISTS "
                "FOR (s:SemanticEdge) ON (s.target_id)"
            ),
            (
                "semanticedge_type_idx",
                "CREATE INDEX semanticedge_type_idx IF NOT EXISTS "
                "FOR (s:SemanticEdge) ON (s.relationship_type)"
            ),
            (
                "semanticedge_confidence_idx",
                "CREATE INDEX semanticedge_confidence_idx IF NOT EXISTS "
                "FOR (s:SemanticEdge) ON (s.confidence)"
            ),
            (
                "semanticedge_created_idx",
                "CREATE INDEX semanticedge_created_idx IF NOT EXISTS "
                "FOR (s:SemanticEdge) ON (s.created_at)"
            ),

            # ═══════════════════════════════════════════════════════════════
            # CHAT ROOM ACCESS CONTROL (Audit 6 - Session 4)
            # ═══════════════════════════════════════════════════════════════

            # ChatRoom indexes
            (
                "chatroom_owner_idx",
                "CREATE INDEX chatroom_owner_idx IF NOT EXISTS "
                "FOR (r:ChatRoom) ON (r.owner_id)"
            ),
            (
                "chatroom_visibility_idx",
                "CREATE INDEX chatroom_visibility_idx IF NOT EXISTS "
                "FOR (r:ChatRoom) ON (r.visibility)"
            ),
            (
                "chatroom_created_idx",
                "CREATE INDEX chatroom_created_idx IF NOT EXISTS "
                "FOR (r:ChatRoom) ON (r.created_at)"
            ),

            # RoomMember indexes (stored as relationship properties or separate nodes)
            (
                "roommember_user_idx",
                "CREATE INDEX roommember_user_idx IF NOT EXISTS "
                "FOR (m:RoomMember) ON (m.user_id)"
            ),
            (
                "roommember_room_idx",
                "CREATE INDEX roommember_room_idx IF NOT EXISTS "
                "FOR (m:RoomMember) ON (m.room_id)"
            ),
            (
                "roommember_role_idx",
                "CREATE INDEX roommember_role_idx IF NOT EXISTS "
                "FOR (m:RoomMember) ON (m.role)"
            ),

            # ChatMessage indexes
            (
                "chatmessage_room_idx",
                "CREATE INDEX chatmessage_room_idx IF NOT EXISTS "
                "FOR (m:ChatMessage) ON (m.room_id)"
            ),
            (
                "chatmessage_sender_idx",
                "CREATE INDEX chatmessage_sender_idx IF NOT EXISTS "
                "FOR (m:ChatMessage) ON (m.sender_id)"
            ),
            (
                "chatmessage_created_idx",
                "CREATE INDEX chatmessage_created_idx IF NOT EXISTS "
                "FOR (m:ChatMessage) ON (m.created_at)"
            ),
        ]

        results = {}
        for name, query in indexes:
            try:
                await self.client.execute(query)
                results[name] = True
                logger.debug(f"Created index: {name}")
            except ClientError as e:
                # Syntax or client-side error - likely a bug in the query
                results[name] = False
                logger.error(f"Client error creating index: {name}", error=str(e))
            except DatabaseError as e:
                # Database-level error - may be transient or index already exists
                results[name] = False
                logger.error(f"Database error creating index: {name}", error=str(e))
            except ServiceUnavailable as e:
                # Connection lost - re-raise as this is fatal
                logger.critical(f"Database unavailable while creating index: {name}", error=str(e))
                raise
            except Exception as e:
                # Unexpected error - log with full type info
                results[name] = False
                logger.error(
                    f"Unexpected error creating index: {name}",
                    error_type=type(e).__name__,
                    error=str(e)
                )

        return results

    async def create_vector_indexes(self) -> dict[str, bool]:
        """
        Create vector indexes for semantic search.

        Neo4j 5.x supports native vector indexing.
        """

        vector_indexes = [
            # Capsule embeddings for semantic search
            (
                "capsule_embeddings",
                f"""
                CREATE VECTOR INDEX capsule_embeddings IF NOT EXISTS
                FOR (c:Capsule) ON c.embedding
                OPTIONS {{
                    indexConfig: {{
                        `vector.dimensions`: {settings.embedding_dimensions},
                        `vector.similarity_function`: 'cosine'
                    }}
                }}
                """
            ),
        ]

        results = {}
        for name, query in vector_indexes:
            try:
                await self.client.execute(query)
                results[name] = True
                logger.info(f"Created vector index: {name}")
            except ClientError as e:
                # Vector indexes not supported or syntax error
                results[name] = False
                logger.warning(
                    f"Client error creating vector index: {name}",
                    error=str(e),
                    hint="Vector indexes require Neo4j 5.x with vector index support",
                )
            except DatabaseError as e:
                # Database-level error - may be version incompatibility
                results[name] = False
                logger.warning(
                    f"Database error creating vector index: {name}",
                    error=str(e),
                    hint="Vector indexes require Neo4j 5.x with vector index support",
                )
            except ServiceUnavailable as e:
                # Connection lost - re-raise as this is fatal
                logger.critical(f"Database unavailable while creating vector index: {name}", error=str(e))
                raise
            except Exception as e:
                # Unexpected error - log with full type info
                results[name] = False
                logger.warning(
                    f"Unexpected error creating vector index: {name}",
                    error_type=type(e).__name__,
                    error=str(e),
                    hint="Vector indexes require Neo4j 5.x with vector index support",
                )

        return results

    async def drop_all(self, force: bool = False) -> dict[str, bool]:
        """
        Drop all schema elements (for testing/reset).

        WARNING: This will delete all constraints and indexes!

        Args:
            force: Must be True to allow execution in production

        Raises:
            RuntimeError: If called in production without force=True
        """
        from forge.config import get_settings

        settings = get_settings()

        # SECURITY: Block dangerous operations in production
        if settings.app_env == "production" and not force:
            logger.error(
                "drop_all_blocked",
                reason="Cannot drop schema in production without force=True",
                environment=settings.app_env
            )
            raise RuntimeError(
                "drop_all() is blocked in production environment. "
                "Set force=True only if you absolutely need to reset the schema. "
                "This action is irreversible and will delete all constraints and indexes."
            )

        logger.warning(
            "drop_all_executing",
            environment=settings.app_env,
            force=force,
            warning="Dropping all schema elements - this action is destructive"
        )

        results = {}

        # Get all constraints
        constraints = await self.client.execute(
            "SHOW CONSTRAINTS YIELD name RETURN name"
        )

        for constraint in constraints:
            name = constraint.get("name")
            if name:
                # SECURITY FIX (Audit 2): Validate identifier before using in DROP
                if not _validate_identifier(name):
                    logger.warning(f"Skipping invalid constraint name: {name[:50]}")
                    results["drop_constraint_invalid"] = False
                    continue
                try:
                    await self.client.execute(f"DROP CONSTRAINT {name} IF EXISTS")
                    results[f"drop_constraint_{name}"] = True
                except ClientError as e:
                    results[f"drop_constraint_{name}"] = False
                    logger.error(f"Client error dropping constraint: {name}", error=str(e))
                except DatabaseError as e:
                    results[f"drop_constraint_{name}"] = False
                    logger.error(f"Database error dropping constraint: {name}", error=str(e))
                except ServiceUnavailable as e:
                    logger.critical(f"Database unavailable while dropping constraint: {name}", error=str(e))
                    raise
                except Exception as e:
                    results[f"drop_constraint_{name}"] = False
                    logger.error(
                        f"Unexpected error dropping constraint: {name}",
                        error_type=type(e).__name__,
                        error=str(e)
                    )

        # Get all indexes
        indexes = await self.client.execute(
            "SHOW INDEXES YIELD name RETURN name"
        )

        for index in indexes:
            name = index.get("name")
            if name:
                # SECURITY FIX (Audit 2): Validate identifier before using in DROP
                if not _validate_identifier(name):
                    logger.warning(f"Skipping invalid index name: {name[:50]}")
                    results["drop_index_invalid"] = False
                    continue
                try:
                    await self.client.execute(f"DROP INDEX {name} IF EXISTS")
                    results[f"drop_index_{name}"] = True
                except ClientError as e:
                    results[f"drop_index_{name}"] = False
                    logger.error(f"Client error dropping index: {name}", error=str(e))
                except DatabaseError as e:
                    results[f"drop_index_{name}"] = False
                    logger.error(f"Database error dropping index: {name}", error=str(e))
                except ServiceUnavailable as e:
                    logger.critical(f"Database unavailable while dropping index: {name}", error=str(e))
                    raise
                except Exception as e:
                    results[f"drop_index_{name}"] = False
                    logger.error(
                        f"Unexpected error dropping index: {name}",
                        error_type=type(e).__name__,
                        error=str(e)
                    )

        return results

    async def verify_schema(self) -> dict[str, Any]:
        """
        Verify that all required schema elements exist.

        Returns:
            Verification results with missing elements
        """
        expected_constraints = {
            "capsule_id_unique",
            "user_id_unique",
            "user_username_unique",
            "user_email_unique",
            "overlay_id_unique",
            "overlay_name_unique",
            "proposal_id_unique",
            "vote_id_unique",
            "auditlog_id_unique",
            "event_id_unique",
            # Graph extensions
            "capsuleversion_id_unique",
            "trustsnapshot_id_unique",
            "graphsnapshot_id_unique",
            "semanticedge_id_unique",
            # Chat room access control (Audit 6 - Session 4)
            "chatroom_id_unique",
            "chatroom_invite_code_unique",
            "chatmessage_id_unique",
        }

        expected_indexes = {
            "capsule_type_idx",
            "capsule_owner_idx",
            "capsule_trust_idx",
            "capsule_created_idx",
            "user_role_idx",
            "user_active_idx",
            "user_trust_idx",
            "overlay_state_idx",
            "overlay_trust_idx",
            "proposal_status_idx",
            "proposal_proposer_idx",
            "audit_entity_idx",
            "audit_user_idx",
            "audit_timestamp_idx",
            "audit_correlation_idx",
            "event_type_idx",
            "event_source_idx",
            "event_timestamp_idx",
            # Graph extensions: Temporal
            "version_capsule_idx",
            "version_timestamp_idx",
            "version_type_idx",
            "version_creator_idx",
            "trustsnapshot_entity_idx",
            "trustsnapshot_time_idx",
            "trustsnapshot_type_idx",
            "graphsnapshot_time_idx",
            # Graph extensions: Semantic
            "semanticedge_source_idx",
            "semanticedge_target_idx",
            "semanticedge_type_idx",
            "semanticedge_confidence_idx",
            "semanticedge_created_idx",
            # Chat room access control (Audit 6 - Session 4)
            "chatroom_owner_idx",
            "chatroom_visibility_idx",
            "chatroom_created_idx",
            "roommember_user_idx",
            "roommember_room_idx",
            "roommember_role_idx",
            "chatmessage_room_idx",
            "chatmessage_sender_idx",
            "chatmessage_created_idx",
        }

        expected_vector_indexes = {
            "capsule_embeddings",
        }

        # Get existing constraints
        constraints = await self.client.execute(
            "SHOW CONSTRAINTS YIELD name RETURN name"
        )
        existing_constraints = {c["name"] for c in constraints}

        # Get existing indexes
        indexes = await self.client.execute(
            "SHOW INDEXES YIELD name, type RETURN name, type"
        )
        existing_indexes = {i["name"] for i in indexes if i.get("type") != "VECTOR"}
        existing_vector = {i["name"] for i in indexes if i.get("type") == "VECTOR"}

        return {
            "constraints": {
                "expected": len(expected_constraints),
                "found": len(existing_constraints & expected_constraints),
                "missing": list(expected_constraints - existing_constraints),
            },
            "indexes": {
                "expected": len(expected_indexes),
                "found": len(existing_indexes & expected_indexes),
                "missing": list(expected_indexes - existing_indexes),
            },
            "vector_indexes": {
                "expected": len(expected_vector_indexes),
                "found": len(existing_vector & expected_vector_indexes),
                "missing": list(expected_vector_indexes - existing_vector),
            },
            "is_complete": (
                len(expected_constraints - existing_constraints) == 0
                and len(expected_indexes - existing_indexes) == 0
            ),
        }
