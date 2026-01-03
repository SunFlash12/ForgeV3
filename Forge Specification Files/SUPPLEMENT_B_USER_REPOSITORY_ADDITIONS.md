# Forge V3 - Phase 1 Supplement: User Repository Additions

**Purpose:** Add missing methods to UserRepository, including `anonymize()` for GDPR compliance and `list_active()` for governance eligibility.

**Add these methods to:** `forge/core/users/repository.py`

---

```python
# Additional methods for forge/core/users/repository.py

class UserRepository:
    # ... existing methods from Phase 1 ...
    
    async def list_active(self) -> list[User]:
        """
        List all active users.
        
        Used for calculating total eligible vote weight in governance.
        Excludes quarantined and inactive users.
        """
        results = await self._neo4j.run("""
            MATCH (u:User)
            WHERE u.is_active = true 
              AND u.trust_level <> 'quarantine'
            RETURN u
            ORDER BY u.created_at
        """)
        
        return [self._map_to_user(dict(r["u"])) for r in results]
    
    async def list_by_trust_level(
        self,
        trust_level: TrustLevel,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[User], int]:
        """
        List users filtered by trust level.
        
        Returns (users, total_count).
        """
        params = {
            "trust_level": trust_level.value,
            "skip": (page - 1) * per_page,
            "limit": per_page,
        }
        
        # Get total count
        count_result = await self._neo4j.run_single("""
            MATCH (u:User {trust_level: $trust_level})
            RETURN count(u) as total
        """, params)
        total = count_result["total"] if count_result else 0
        
        # Get paginated results
        results = await self._neo4j.run("""
            MATCH (u:User {trust_level: $trust_level})
            RETURN u
            ORDER BY u.created_at DESC
            SKIP $skip
            LIMIT $limit
        """, params)
        
        users = [self._map_to_user(dict(r["u"])) for r in results]
        return users, total
    
    async def anonymize(self, user_id: UUID) -> None:
        """
        Anonymize a user's personal data for GDPR right-to-erasure.
        
        This method:
        1. Replaces email with anonymized placeholder
        2. Removes display name
        3. Removes password hash
        4. Sets account as inactive
        5. Preserves the user node for audit trail integrity
        
        The user record is kept to maintain referential integrity
        with capsules, votes, and audit logs, but all PII is removed.
        """
        anonymized_email = f"deleted-{user_id}@anonymized.forge"
        
        await self._neo4j.run("""
            MATCH (u:User {id: $id})
            SET u.email = $anonymized_email,
                u.display_name = null,
                u.password_hash = null,
                u.is_active = false,
                u.mfa_enabled = false,
                u.anonymized_at = datetime(),
                u.updated_at = datetime()
        """, {
            "id": str(user_id),
            "anonymized_email": anonymized_email,
        })
        
        logger.info("user_anonymized", user_id=str(user_id))
    
    async def hard_delete(self, user_id: UUID) -> bool:
        """
        Permanently delete a user and all relationships.
        
        WARNING: This is destructive and should rarely be used.
        Prefer anonymize() for GDPR compliance while maintaining
        audit trail integrity.
        
        This will fail if the user owns capsules or has cast votes,
        as those relationships must be handled first.
        """
        # Check for owned capsules
        capsule_check = await self._neo4j.run_single("""
            MATCH (c:Capsule {owner_id: $id})
            RETURN count(c) as count
        """, {"id": str(user_id)})
        
        if capsule_check and capsule_check["count"] > 0:
            raise ConflictError(
                f"Cannot delete user: owns {capsule_check['count']} capsules. "
                "Delete or reassign capsules first."
            )
        
        # Delete user and relationships
        result = await self._neo4j.run_single("""
            MATCH (u:User {id: $id})
            DETACH DELETE u
            RETURN true as deleted
        """, {"id": str(user_id)})
        
        if result and result.get("deleted"):
            logger.info("user_hard_deleted", user_id=str(user_id))
            return True
        return False
    
    async def update(
        self,
        user_id: UUID,
        data: UserUpdate,
    ) -> User:
        """
        Update user profile fields.
        
        Only updates provided fields (partial update).
        """
        set_parts = ["u.updated_at = datetime()"]
        params: dict[str, Any] = {"id": str(user_id)}
        
        if data.display_name is not None:
            set_parts.append("u.display_name = $display_name")
            params["display_name"] = data.display_name
        
        query = f"""
            MATCH (u:User {{id: $id}})
            SET {', '.join(set_parts)}
            RETURN u
        """
        
        result = await self._neo4j.run_single(query, params)
        
        if not result:
            raise NotFoundError("User", str(user_id))
        
        logger.info("user_updated", user_id=str(user_id))
        return self._map_to_user(dict(result["u"]))
    
    async def add_role(self, user_id: UUID, role: str) -> User:
        """Add a role to a user."""
        result = await self._neo4j.run_single("""
            MATCH (u:User {id: $id})
            SET u.roles = CASE 
                WHEN $role IN u.roles THEN u.roles 
                ELSE u.roles + $role 
            END,
            u.updated_at = datetime()
            RETURN u
        """, {"id": str(user_id), "role": role})
        
        if not result:
            raise NotFoundError("User", str(user_id))
        
        logger.info("role_added", user_id=str(user_id), role=role)
        return self._map_to_user(dict(result["u"]))
    
    async def remove_role(self, user_id: UUID, role: str) -> User:
        """Remove a role from a user."""
        result = await self._neo4j.run_single("""
            MATCH (u:User {id: $id})
            SET u.roles = [r IN u.roles WHERE r <> $role],
                u.updated_at = datetime()
            RETURN u
        """, {"id": str(user_id), "role": role})
        
        if not result:
            raise NotFoundError("User", str(user_id))
        
        logger.info("role_removed", user_id=str(user_id), role=role)
        return self._map_to_user(dict(result["u"]))
    
    async def search_by_email(
        self,
        email_pattern: str,
        limit: int = 10,
    ) -> list[User]:
        """
        Search users by email pattern.
        
        Useful for admin user lookup.
        """
        results = await self._neo4j.run("""
            MATCH (u:User)
            WHERE u.email CONTAINS $pattern
            RETURN u
            LIMIT $limit
        """, {"pattern": email_pattern.lower(), "limit": limit})
        
        return [self._map_to_user(dict(r["u"])) for r in results]
    
    async def get_user_stats(self, user_id: UUID) -> dict:
        """
        Get statistics for a user.
        
        Includes capsule count, vote count, etc.
        """
        result = await self._neo4j.run_single("""
            MATCH (u:User {id: $id})
            OPTIONAL MATCH (c:Capsule {owner_id: $id})
            OPTIONAL MATCH (v:Vote {voter_id: $id})
            RETURN u,
                   count(DISTINCT c) as capsule_count,
                   count(DISTINCT v) as vote_count
        """, {"id": str(user_id)})
        
        if not result:
            raise NotFoundError("User", str(user_id))
        
        user = self._map_to_user(dict(result["u"]))
        
        return {
            "user": user,
            "capsule_count": result["capsule_count"],
            "vote_count": result["vote_count"],
        }
```

---

## Capsule Repository Addition

Add this method to CapsuleRepository for GDPR support:

```python
# Add to forge/core/capsules/repository.py

async def list_by_owner(
    self,
    owner_id: UUID,
    include_deleted: bool = False,
) -> list[Capsule]:
    """
    List all capsules owned by a user.
    
    Used for GDPR data access requests.
    """
    deleted_clause = "" if include_deleted else "AND c.is_deleted = false"
    
    results = await self._neo4j.run(f"""
        MATCH (c:Capsule {{owner_id: $owner_id}})
        WHERE true {deleted_clause}
        OPTIONAL MATCH (c)-[:DERIVED_FROM]->(parent:Capsule)
        RETURN c, parent.id as parent_id
        ORDER BY c.created_at DESC
    """, {"owner_id": str(owner_id)})
    
    capsules = []
    for record in results:
        data = dict(record["c"])
        data["parent_id"] = record.get("parent_id")
        capsules.append(self._map_to_capsule(data))
    
    return capsules

async def hard_delete(self, capsule_id: UUID) -> bool:
    """
    Permanently delete a capsule (for GDPR erasure).
    
    WARNING: This is destructive. Updates children to remove
    the parent reference before deletion.
    """
    async with self._neo4j.transaction() as tx:
        # Remove parent references from children
        await tx.run("""
            MATCH (child:Capsule)-[r:DERIVED_FROM]->(parent:Capsule {id: $id})
            DELETE r
        """, {"id": str(capsule_id)})
        
        # Delete the capsule
        result = await tx.run("""
            MATCH (c:Capsule {id: $id})
            DETACH DELETE c
            RETURN true as deleted
        """, {"id": str(capsule_id)})
        
        record = await result.single()
        
    if record and record.get("deleted"):
        logger.info("capsule_hard_deleted", capsule_id=str(capsule_id))
        return True
    return False

async def transfer_ownership(
    self,
    capsule_id: UUID,
    new_owner_id: UUID,
) -> Capsule:
    """
    Transfer capsule ownership to another user.
    
    Useful when a user leaves and their knowledge should
    be preserved under organizational ownership.
    """
    result = await self._neo4j.run_single("""
        MATCH (c:Capsule {id: $capsule_id})
        SET c.owner_id = $new_owner_id,
            c.updated_at = datetime()
        RETURN c
    """, {
        "capsule_id": str(capsule_id),
        "new_owner_id": str(new_owner_id),
    })
    
    if not result:
        raise NotFoundError("Capsule", str(capsule_id))
    
    logger.info(
        "capsule_ownership_transferred",
        capsule_id=str(capsule_id),
        new_owner_id=str(new_owner_id),
    )
    return self._map_to_capsule(dict(result["c"]))
```
