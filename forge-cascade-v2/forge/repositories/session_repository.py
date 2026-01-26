"""
Session Repository

Repository for Session CRUD operations with Redis caching.
Handles session tracking with IP and User-Agent binding (Audit 6 - Session 2).
"""

import asyncio
import json
import time
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import structlog

from forge.config import get_settings
from forge.database.client import Neo4jClient
from forge.models.session import (
    Session,
    SessionCreate,
    SessionStatus,
)

settings = get_settings()
logger = structlog.get_logger(__name__)

# Try to import redis
try:
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    aioredis = None  # type: ignore[assignment]
    REDIS_AVAILABLE = False


class SessionCache:
    """
    Cache for session data to optimize validation performance.

    Uses Redis when available, falls back to in-memory cache.
    Following the same pattern as TokenVersionCache for consistency.
    """

    _cache: dict[str, tuple[dict[str, Any], float]] = {}  # jti -> (session_dict, expiry_timestamp)
    _redis_prefix: str = "forge:session:"
    _async_lock: asyncio.Lock | None = None
    _max_cache_size: int = 50000  # Max in-memory entries

    @classmethod
    def _get_cache_ttl(cls) -> float:
        """Get cache TTL from settings."""
        return float(settings.session_cache_ttl_seconds)

    @classmethod
    def _get_async_lock(cls) -> asyncio.Lock:
        """Get or create the async lock."""
        if cls._async_lock is None:
            cls._async_lock = asyncio.Lock()
        return cls._async_lock

    @classmethod
    def _get_redis_client(cls) -> Any:
        """Get Redis client from TokenBlacklist if available."""
        try:
            from forge.security.tokens import TokenBlacklist
            return TokenBlacklist._redis_client
        except (ImportError, AttributeError):
            return None

    @classmethod
    async def get(cls, jti: str) -> Session | None:
        """
        Get cached session by JTI.

        Args:
            jti: JWT ID (session identifier)

        Returns:
            Session if found and not expired, None otherwise
        """
        if not jti:
            return None

        now = time.time()

        # Try Redis first
        redis_client = cls._get_redis_client()
        if redis_client and settings.session_cache_enabled:
            try:
                key = f"{cls._redis_prefix}{jti}"
                cached = await redis_client.get(key)
                if cached:
                    session_dict = json.loads(cached)
                    return Session.model_validate(session_dict)
            except (ConnectionError, TimeoutError, OSError) as e:
                logger.warning("session_cache_redis_error", error=str(e), operation="get")

        # Try in-memory cache
        async with cls._get_async_lock():
            if jti in cls._cache:
                session_dict, expiry = cls._cache[jti]
                if now < expiry:
                    return Session.model_validate(session_dict)
                # Expired, remove from cache
                cls._cache.pop(jti, None)

        return None

    @classmethod
    async def set(cls, jti: str, session: Session) -> None:
        """
        Cache a session.

        Args:
            jti: JWT ID (session identifier)
            session: Session to cache
        """
        if not jti or not settings.session_cache_enabled:
            return

        now = time.time()
        cache_ttl = cls._get_cache_ttl()
        ttl_seconds = int(cache_ttl)
        session_dict = session.model_dump(mode="json")

        # Try Redis first
        redis_client = cls._get_redis_client()
        if redis_client:
            try:
                key = f"{cls._redis_prefix}{jti}"
                await redis_client.setex(key, ttl_seconds, json.dumps(session_dict))
                return
            except (ConnectionError, TimeoutError, OSError) as e:
                logger.warning("session_cache_redis_error", error=str(e), operation="set")

        # Fall back to in-memory cache
        async with cls._get_async_lock():
            # Evict oldest entries if at capacity
            while len(cls._cache) >= cls._max_cache_size:
                oldest_jti = min(cls._cache.keys(), key=lambda k: cls._cache[k][1])
                cls._cache.pop(oldest_jti, None)

            cls._cache[jti] = (session_dict, now + cache_ttl)

    @classmethod
    async def invalidate(cls, jti: str) -> None:
        """
        Remove session from cache.

        Args:
            jti: JWT ID (session identifier)
        """
        if not jti:
            return

        # Invalidate Redis cache
        redis_client = cls._get_redis_client()
        if redis_client:
            try:
                key = f"{cls._redis_prefix}{jti}"
                await redis_client.delete(key)
            except (ConnectionError, TimeoutError, OSError) as e:
                logger.warning("session_cache_redis_error", error=str(e), operation="invalidate")

        # Invalidate in-memory cache
        async with cls._get_async_lock():
            cls._cache.pop(jti, None)

        logger.debug("session_cache_invalidated", jti=jti[:16] + "...")

    @classmethod
    async def clear(cls) -> None:
        """Clear entire cache (for testing)."""
        redis_client = cls._get_redis_client()
        if redis_client:
            try:
                cursor = 0
                while True:
                    cursor, keys = await redis_client.scan(
                        cursor, match=f"{cls._redis_prefix}*", count=100
                    )
                    if keys:
                        await redis_client.delete(*keys)
                    if cursor == 0:
                        break
            except (ConnectionError, TimeoutError, OSError):
                pass  # Best-effort cache clear

        async with cls._get_async_lock():
            cls._cache.clear()


class SessionRepository:
    """
    Repository for Session entities.

    Provides CRUD operations with caching for session tracking
    with IP and User-Agent binding.
    """

    def __init__(self, client: Neo4jClient):
        """Initialize repository with database client."""
        self.client = client
        self.logger = structlog.get_logger(self.__class__.__name__)

    def _generate_id(self) -> str:
        """Generate a new unique ID."""
        return str(uuid4())

    def _now(self) -> datetime:
        """Get current UTC timestamp (timezone-aware)."""
        return datetime.now(UTC)

    async def create(self, data: SessionCreate) -> Session:
        """
        Create a new session.

        Args:
            data: Session creation data

        Returns:
            Created session
        """
        now = self._now()
        session_id = data.token_jti  # Use JTI as session ID for simplicity

        # Hash user agent for comparison
        ua_hash = Session.hash_user_agent(data.user_agent)

        query = """
        CREATE (s:Session {
            id: $id,
            user_id: $user_id,
            token_jti: $token_jti,
            token_type: $token_type,
            initial_ip: $ip_address,
            initial_user_agent: $user_agent,
            initial_user_agent_hash: $ua_hash,
            last_ip: $ip_address,
            last_user_agent: $user_agent,
            last_user_agent_hash: $ua_hash,
            last_activity: $now,
            request_count: 1,
            ip_change_count: 0,
            user_agent_change_count: 0,
            ip_history: $ip_history,
            expires_at: $expires_at,
            status: $status,
            revoked_at: null,
            revoked_reason: null,
            created_at: $now,
            updated_at: $now
        })
        RETURN s {.*} AS session
        """

        # Initialize IP history with first entry
        ip_history = [{
            "ip": data.ip_address,
            "timestamp": now.isoformat(),
            "action": "created"
        }]

        params = {
            "id": session_id,
            "user_id": data.user_id,
            "token_jti": data.token_jti,
            "token_type": data.token_type,
            "ip_address": data.ip_address,
            "user_agent": data.user_agent,
            "ua_hash": ua_hash,
            "now": now.isoformat(),
            "ip_history": json.dumps(ip_history),
            "expires_at": data.expires_at.isoformat(),
            "status": SessionStatus.ACTIVE.value,
        }

        result = await self.client.execute_single(query, params)

        if result and result.get("session"):
            session_data = result["session"]
            # Parse JSON fields
            if isinstance(session_data.get("ip_history"), str):
                session_data["ip_history"] = json.loads(session_data["ip_history"])

            session = Session.model_validate(session_data)

            # Cache the session
            await SessionCache.set(data.token_jti, session)

            self.logger.info(
                "session_created",
                session_id=session_id,
                user_id=data.user_id,
                ip=data.ip_address[:16] + "..." if len(data.ip_address) > 16 else data.ip_address,
            )
            return session

        raise RuntimeError(f"Failed to create session for user {data.user_id}")

    async def get_by_jti(self, jti: str) -> Session | None:
        """
        Get session by JWT ID with caching.

        Args:
            jti: JWT ID (session identifier)

        Returns:
            Session if found, None otherwise
        """
        if not jti:
            return None

        # Try cache first
        cached = await SessionCache.get(jti)
        if cached:
            return cached

        # Query database
        query = """
        MATCH (s:Session {token_jti: $jti})
        WHERE s.status <> 'expired'
        RETURN s {.*} AS session
        """

        result = await self.client.execute_single(query, {"jti": jti})

        if result and result.get("session"):
            session_data = result["session"]
            # Parse JSON fields
            if isinstance(session_data.get("ip_history"), str):
                session_data["ip_history"] = json.loads(session_data["ip_history"])

            session = Session.model_validate(session_data)

            # Check if expired
            if datetime.now(UTC) >= session.expires_at:
                await self._mark_expired(jti)
                return None

            # Cache for future lookups
            await SessionCache.set(jti, session)
            return session

        return None

    async def update_activity(
        self,
        jti: str,
        ip_address: str,
        user_agent: str | None,
    ) -> tuple[Session | None, dict[str, Any]]:
        """
        Update session activity and detect binding changes.

        Args:
            jti: JWT ID (session identifier)
            ip_address: Current request IP
            user_agent: Current request User-Agent

        Returns:
            Tuple of (updated_session, changes_dict)
            changes_dict contains: {ip_changed: bool, ua_changed: bool, old_ip, new_ip, etc.}
        """
        session = await self.get_by_jti(jti)
        if not session:
            return None, {}

        now = self._now()
        changes: dict[str, Any] = {
            "ip_changed": False,
            "user_agent_changed": False,
        }

        # Detect IP change
        new_ip_change_count = session.ip_change_count
        new_ip_history = list(session.ip_history)

        if ip_address != session.last_ip:
            changes["ip_changed"] = True
            changes["old_ip"] = session.last_ip
            changes["new_ip"] = ip_address
            new_ip_change_count += 1

            # Add to IP history (keep max configured entries)
            new_ip_history.insert(0, {
                "ip": ip_address,
                "timestamp": now.isoformat(),
                "previous_ip": session.last_ip,
            })
            max_history = settings.max_ip_history_per_session
            new_ip_history = new_ip_history[:max_history]

        # Detect User-Agent change
        new_ua_change_count = session.user_agent_change_count
        new_ua_hash = Session.hash_user_agent(user_agent)

        if new_ua_hash != session.last_user_agent_hash:
            changes["user_agent_changed"] = True
            changes["old_user_agent"] = session.last_user_agent
            changes["new_user_agent"] = user_agent
            new_ua_change_count += 1

        # Update session in database
        query = """
        MATCH (s:Session {token_jti: $jti})
        SET s.last_ip = $ip_address,
            s.last_user_agent = $user_agent,
            s.last_user_agent_hash = $ua_hash,
            s.last_activity = $now,
            s.request_count = s.request_count + 1,
            s.ip_change_count = $ip_change_count,
            s.user_agent_change_count = $ua_change_count,
            s.ip_history = $ip_history,
            s.updated_at = $now
        RETURN s {.*} AS session
        """

        params = {
            "jti": jti,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "ua_hash": new_ua_hash,
            "now": now.isoformat(),
            "ip_change_count": new_ip_change_count,
            "ua_change_count": new_ua_change_count,
            "ip_history": json.dumps(new_ip_history),
        }

        result = await self.client.execute_single(query, params)

        if result and result.get("session"):
            session_data = result["session"]
            if isinstance(session_data.get("ip_history"), str):
                session_data["ip_history"] = json.loads(session_data["ip_history"])

            updated_session = Session.model_validate(session_data)

            # Update cache
            await SessionCache.set(jti, updated_session)

            return updated_session, changes

        return session, changes

    async def get_user_sessions(
        self,
        user_id: str,
        include_expired: bool = False,
        limit: int = 20,
    ) -> list[Session]:
        """
        Get all sessions for a user.

        Args:
            user_id: User ID
            include_expired: Whether to include expired/revoked sessions
            limit: Maximum sessions to return

        Returns:
            List of sessions, most recent first
        """
        if include_expired:
            query = """
            MATCH (s:Session {user_id: $user_id})
            RETURN s {.*} AS session
            ORDER BY s.last_activity DESC
            LIMIT $limit
            """
        else:
            query = """
            MATCH (s:Session {user_id: $user_id})
            WHERE s.status IN ['active', 'suspicious']
              AND s.expires_at > $now
            RETURN s {.*} AS session
            ORDER BY s.last_activity DESC
            LIMIT $limit
            """

        # SECURITY FIX (Audit 4): Bound limit consistently
        params = {
            "user_id": user_id,
            "limit": max(1, min(int(limit), 100)),
            "now": self._now().isoformat(),
        }

        results = await self.client.execute(query, params)
        sessions = []

        for r in results:
            if r.get("session"):
                session_data = r["session"]
                if isinstance(session_data.get("ip_history"), str):
                    session_data["ip_history"] = json.loads(session_data["ip_history"])
                sessions.append(Session.model_validate(session_data))

        return sessions

    async def revoke_session(
        self,
        jti: str,
        reason: str | None = None,
    ) -> bool:
        """
        Revoke a specific session.

        Args:
            jti: JWT ID (session identifier)
            reason: Reason for revocation

        Returns:
            True if session was revoked
        """
        now = self._now()

        query = """
        MATCH (s:Session {token_jti: $jti})
        WHERE s.status IN ['active', 'suspicious']
        SET s.status = 'revoked',
            s.revoked_at = $now,
            s.revoked_reason = $reason,
            s.updated_at = $now
        RETURN s.id AS id
        """

        result = await self.client.execute_single(query, {
            "jti": jti,
            "now": now.isoformat(),
            "reason": reason or "User requested revocation",
        })

        if result and result.get("id"):
            # Invalidate cache
            await SessionCache.invalidate(jti)

            self.logger.info(
                "session_revoked",
                jti=jti[:16] + "...",
                reason=reason,
            )
            return True

        return False

    async def revoke_user_sessions(
        self,
        user_id: str,
        except_jti: str | None = None,
        reason: str | None = None,
    ) -> int:
        """
        Revoke all sessions for a user.

        Args:
            user_id: User ID
            except_jti: JTI to exclude from revocation (current session)
            reason: Reason for revocation

        Returns:
            Number of sessions revoked
        """
        now = self._now()

        if except_jti:
            query = """
            MATCH (s:Session {user_id: $user_id})
            WHERE s.status IN ['active', 'suspicious']
              AND s.token_jti <> $except_jti
            SET s.status = 'revoked',
                s.revoked_at = $now,
                s.revoked_reason = $reason,
                s.updated_at = $now
            RETURN collect(s.token_jti) AS revoked_jtis
            """
            params = {
                "user_id": user_id,
                "except_jti": except_jti,
                "now": now.isoformat(),
                "reason": reason or "All sessions revoked",
            }
        else:
            query = """
            MATCH (s:Session {user_id: $user_id})
            WHERE s.status IN ['active', 'suspicious']
            SET s.status = 'revoked',
                s.revoked_at = $now,
                s.revoked_reason = $reason,
                s.updated_at = $now
            RETURN collect(s.token_jti) AS revoked_jtis
            """
            params = {
                "user_id": user_id,
                "now": now.isoformat(),
                "reason": reason or "All sessions revoked",
            }

        result = await self.client.execute_single(query, params)

        revoked_jtis = result.get("revoked_jtis", []) if result else []

        # Invalidate cache for all revoked sessions
        for jti in revoked_jtis:
            await SessionCache.invalidate(jti)

        if revoked_jtis:
            self.logger.info(
                "user_sessions_revoked",
                user_id=user_id,
                count=len(revoked_jtis),
                except_jti=except_jti[:16] + "..." if except_jti else None,
            )

        return len(revoked_jtis)

    async def flag_suspicious(
        self,
        jti: str,
        reason: str,
    ) -> bool:
        """
        Flag a session as suspicious.

        Args:
            jti: JWT ID (session identifier)
            reason: Reason for flagging

        Returns:
            True if session was flagged
        """
        now = self._now()

        query = """
        MATCH (s:Session {token_jti: $jti})
        WHERE s.status = 'active'
        SET s.status = 'suspicious',
            s.updated_at = $now
        RETURN s.id AS id
        """

        result = await self.client.execute_single(query, {
            "jti": jti,
            "now": now.isoformat(),
        })

        if result and result.get("id"):
            # Invalidate cache to force refresh
            await SessionCache.invalidate(jti)

            self.logger.warning(
                "session_flagged_suspicious",
                jti=jti[:16] + "...",
                reason=reason,
            )
            return True

        return False

    async def _mark_expired(self, jti: str) -> None:
        """Mark a session as expired."""
        now = self._now()

        query = """
        MATCH (s:Session {token_jti: $jti})
        SET s.status = 'expired',
            s.updated_at = $now
        """

        await self.client.execute(query, {
            "jti": jti,
            "now": now.isoformat(),
        })

        await SessionCache.invalidate(jti)

    async def cleanup_expired(self) -> int:
        """
        Clean up expired sessions.

        Called by scheduler to remove old sessions.

        Returns:
            Number of sessions cleaned up
        """
        now = self._now()

        # Mark expired sessions
        query = """
        MATCH (s:Session)
        WHERE s.status = 'active'
          AND s.expires_at < $now
        SET s.status = 'expired',
            s.updated_at = $now
        RETURN count(s) AS count
        """

        result = await self.client.execute_single(query, {"now": now.isoformat()})
        count = result.get("count", 0) if result else 0

        if count > 0:
            self.logger.info("expired_sessions_cleaned_up", count=count)

        return count

    async def count_active_sessions(self, user_id: str) -> int:
        """Count active sessions for a user."""
        query = """
        MATCH (s:Session {user_id: $user_id})
        WHERE s.status IN ['active', 'suspicious']
          AND s.expires_at > $now
        RETURN count(s) AS count
        """

        result = await self.client.execute_single(query, {
            "user_id": user_id,
            "now": self._now().isoformat(),
        })

        return result.get("count", 0) if result else 0

    async def ensure_indexes(self) -> None:
        """Create necessary database indexes for sessions."""
        indexes = [
            "CREATE CONSTRAINT session_id_unique IF NOT EXISTS FOR (s:Session) REQUIRE s.id IS UNIQUE",
            "CREATE CONSTRAINT session_jti_unique IF NOT EXISTS FOR (s:Session) REQUIRE s.token_jti IS UNIQUE",
            "CREATE INDEX session_user_id IF NOT EXISTS FOR (s:Session) ON (s.user_id)",
            "CREATE INDEX session_expires_at IF NOT EXISTS FOR (s:Session) ON (s.expires_at)",
            "CREATE INDEX session_status IF NOT EXISTS FOR (s:Session) ON (s.status)",
        ]

        for index_query in indexes:
            try:
                await self.client.execute(index_query)
            except (RuntimeError, OSError, ValueError) as e:
                # Index may already exist
                self.logger.debug("index_creation_skipped", query=index_query[:50], error=str(e))
