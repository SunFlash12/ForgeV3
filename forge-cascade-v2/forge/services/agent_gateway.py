"""
Agent Knowledge Gateway Service

Provides AI agents with programmatic access to Forge's knowledge graph.
"""

import asyncio
import hashlib
import secrets
import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Any, AsyncIterator

from forge.models.agent_gateway import (
    AgentSession,
    AgentQuery,
    QueryResult,
    QueryType,
    ResponseFormat,
    AgentCapability,
    AgentTrustLevel,
    CapsuleAccess,
    AccessType,
    AgentCapsuleCreation,
    GatewayStats,
    StreamChunk,
)
from forge.models.capsule import TrustLevel

logger = logging.getLogger(__name__)


class AgentGatewayService:
    """
    Service for managing AI agent access to the knowledge graph.

    Provides:
    - Session management with API key authentication
    - Natural language and structured queries
    - Trust-based access control
    - Rate limiting
    - Usage tracking and analytics
    """

    # Trust level to numeric mapping for comparisons
    TRUST_LEVEL_VALUES = {
        AgentTrustLevel.UNTRUSTED: 0,
        AgentTrustLevel.BASIC: 1,
        AgentTrustLevel.VERIFIED: 2,
        AgentTrustLevel.TRUSTED: 3,
        AgentTrustLevel.SYSTEM: 4,
    }

    # Default capabilities by trust level
    DEFAULT_CAPABILITIES = {
        AgentTrustLevel.UNTRUSTED: [
            AgentCapability.READ_CAPSULES,
        ],
        AgentTrustLevel.BASIC: [
            AgentCapability.READ_CAPSULES,
            AgentCapability.QUERY_GRAPH,
            AgentCapability.SEMANTIC_SEARCH,
            AgentCapability.ACCESS_LINEAGE,
        ],
        AgentTrustLevel.VERIFIED: [
            AgentCapability.READ_CAPSULES,
            AgentCapability.QUERY_GRAPH,
            AgentCapability.SEMANTIC_SEARCH,
            AgentCapability.CREATE_CAPSULES,
            AgentCapability.ACCESS_LINEAGE,
            AgentCapability.VIEW_GOVERNANCE,
        ],
        AgentTrustLevel.TRUSTED: [
            AgentCapability.READ_CAPSULES,
            AgentCapability.QUERY_GRAPH,
            AgentCapability.SEMANTIC_SEARCH,
            AgentCapability.CREATE_CAPSULES,
            AgentCapability.UPDATE_CAPSULES,
            AgentCapability.EXECUTE_CASCADE,
            AgentCapability.ACCESS_LINEAGE,
            AgentCapability.VIEW_GOVERNANCE,
        ],
        AgentTrustLevel.SYSTEM: list(AgentCapability),  # All capabilities
    }

    # Rate limits by trust level (requests per minute, per hour)
    RATE_LIMITS = {
        AgentTrustLevel.UNTRUSTED: (10, 100),
        AgentTrustLevel.BASIC: (60, 1000),
        AgentTrustLevel.VERIFIED: (120, 3000),
        AgentTrustLevel.TRUSTED: (300, 10000),
        AgentTrustLevel.SYSTEM: (1000, 50000),
    }

    def __init__(
        self,
        db_client=None,
        capsule_repo=None,
        query_compiler=None,
        event_system=None,
    ):
        self.db = db_client
        self.capsule_repo = capsule_repo
        self.query_compiler = query_compiler
        self.event_system = event_system

        # In-memory storage (would be Redis in production)
        self._sessions: dict[str, AgentSession] = {}
        self._api_keys: dict[str, str] = {}  # hash -> session_id
        self._rate_limits: dict[str, list[datetime]] = {}  # session_id -> request times
        self._query_cache: dict[str, QueryResult] = {}
        self._access_logs: list[CapsuleAccess] = []

        # Stats
        self._stats = GatewayStats()

    # =========================================================================
    # Session Management
    # =========================================================================

    async def create_session(
        self,
        agent_name: str,
        owner_user_id: str,
        trust_level: AgentTrustLevel = AgentTrustLevel.BASIC,
        capabilities: list[AgentCapability] | None = None,
        allowed_capsule_types: list[str] | None = None,
        expires_in_days: int = 30,
    ) -> tuple[AgentSession, str]:
        """
        Create a new agent session and return (session, api_key).

        The API key is only returned once and should be stored securely.
        """
        # Generate API key
        api_key = f"forge_agent_{secrets.token_urlsafe(32)}"
        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        # Determine capabilities
        if capabilities is None:
            capabilities = self.DEFAULT_CAPABILITIES.get(trust_level, [])

        # Get rate limits
        rpm, rph = self.RATE_LIMITS.get(trust_level, (60, 1000))

        session = AgentSession(
            agent_name=agent_name,
            agent_id=f"agent_{secrets.token_urlsafe(8)}",
            api_key_hash=api_key_hash,
            owner_user_id=owner_user_id,
            trust_level=trust_level,
            capabilities=capabilities,
            allowed_capsule_types=allowed_capsule_types or [],
            requests_per_minute=rpm,
            requests_per_hour=rph,
            expires_at=datetime.now(timezone.utc) + timedelta(days=expires_in_days),
        )

        self._sessions[session.id] = session
        self._api_keys[api_key_hash] = session.id

        self._stats.total_sessions += 1
        self._stats.active_sessions = len([s for s in self._sessions.values() if s.is_active])

        logger.info(
            "agent_session_created",
            session_id=session.id,
            agent_name=agent_name,
            trust_level=trust_level.value,
        )

        return session, api_key

    async def authenticate(self, api_key: str) -> AgentSession | None:
        """Authenticate an agent by API key."""
        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        session_id = self._api_keys.get(api_key_hash)

        if not session_id:
            return None

        session = self._sessions.get(session_id)
        if not session:
            return None

        # Check expiration
        if session.expires_at and datetime.now(timezone.utc) > session.expires_at:
            session.is_active = False
            return None

        if not session.is_active:
            return None

        return session

    async def get_session(self, session_id: str) -> AgentSession | None:
        """Get session by ID."""
        return self._sessions.get(session_id)

    async def revoke_session(self, session_id: str) -> bool:
        """Revoke an agent session."""
        session = self._sessions.get(session_id)
        if not session:
            return False

        session.is_active = False

        # Remove API key mapping
        for key_hash, sid in list(self._api_keys.items()):
            if sid == session_id:
                del self._api_keys[key_hash]

        self._stats.active_sessions = len([s for s in self._sessions.values() if s.is_active])

        logger.info("agent_session_revoked", session_id=session_id)
        return True

    async def list_sessions(
        self,
        owner_user_id: str | None = None,
        active_only: bool = True,
    ) -> list[AgentSession]:
        """List agent sessions."""
        sessions = list(self._sessions.values())

        if owner_user_id:
            sessions = [s for s in sessions if s.owner_user_id == owner_user_id]

        if active_only:
            sessions = [s for s in sessions if s.is_active]

        return sessions

    # =========================================================================
    # Rate Limiting
    # =========================================================================

    async def check_rate_limit(self, session: AgentSession) -> tuple[bool, str | None]:
        """Check if session is within rate limits. Returns (allowed, reason)."""
        now = datetime.now(timezone.utc)
        session_id = session.id

        # Get request history
        requests = self._rate_limits.get(session_id, [])

        # Clean old entries (keep last hour)
        cutoff = now - timedelta(hours=1)
        requests = [r for r in requests if r > cutoff]
        self._rate_limits[session_id] = requests

        # Check per-minute limit
        minute_ago = now - timedelta(minutes=1)
        recent_requests = len([r for r in requests if r > minute_ago])
        if recent_requests >= session.requests_per_minute:
            return False, f"Rate limit exceeded: {session.requests_per_minute}/minute"

        # Check per-hour limit
        if len(requests) >= session.requests_per_hour:
            return False, f"Rate limit exceeded: {session.requests_per_hour}/hour"

        # Record this request
        requests.append(now)
        self._rate_limits[session_id] = requests

        return True, None

    # =========================================================================
    # Query Execution
    # =========================================================================

    async def execute_query(
        self,
        session: AgentSession,
        query: AgentQuery,
    ) -> QueryResult:
        """Execute an agent query against the knowledge graph."""
        start_time = datetime.now(timezone.utc)

        # Check rate limit
        allowed, reason = await self.check_rate_limit(session)
        if not allowed:
            return QueryResult(
                query_id=query.id,
                session_id=session.id,
                success=False,
                error=reason,
                error_code="RATE_LIMITED",
            )

        # Check capability
        required_capability = self._get_required_capability(query.query_type)
        if required_capability and required_capability not in session.capabilities:
            return QueryResult(
                query_id=query.id,
                session_id=session.id,
                success=False,
                error=f"Missing capability: {required_capability.value}",
                error_code="FORBIDDEN",
            )

        # Check cache
        cache_key = self._get_cache_key(query)
        if cache_key in self._query_cache:
            cached = self._query_cache[cache_key]
            cached.cache_hit = True
            return cached

        try:
            # Execute based on query type
            if query.query_type == QueryType.NATURAL_LANGUAGE:
                result = await self._execute_nl_query(session, query)
            elif query.query_type == QueryType.SEMANTIC_SEARCH:
                result = await self._execute_semantic_search(session, query)
            elif query.query_type == QueryType.GRAPH_TRAVERSE:
                result = await self._execute_graph_traverse(session, query)
            elif query.query_type == QueryType.DIRECT_CYPHER:
                result = await self._execute_direct_cypher(session, query)
            elif query.query_type == QueryType.AGGREGATION:
                result = await self._execute_aggregation(session, query)
            else:
                result = QueryResult(
                    query_id=query.id,
                    session_id=session.id,
                    success=False,
                    error=f"Unknown query type: {query.query_type}",
                    error_code="INVALID_QUERY_TYPE",
                )

            # Calculate execution time
            end_time = datetime.now(timezone.utc)
            result.execution_time_ms = int((end_time - start_time).total_seconds() * 1000)

            # Update session stats
            session.total_requests += 1
            session.total_tokens += result.tokens_used
            session.last_request_at = end_time

            # Update stats
            self._stats.queries_today += 1
            self._stats.queries_this_hour += 1
            self._stats.queries_by_type[query.query_type.value] = (
                self._stats.queries_by_type.get(query.query_type.value, 0) + 1
            )
            self._stats.queries_by_trust[session.trust_level.value] = (
                self._stats.queries_by_trust.get(session.trust_level.value, 0) + 1
            )

            # Cache successful results
            if result.success and cache_key:
                self._query_cache[cache_key] = result

            return result

        except Exception as e:
            logger.exception("agent_query_failed", query_id=query.id)
            self._stats.error_count += 1

            return QueryResult(
                query_id=query.id,
                session_id=session.id,
                success=False,
                error=str(e),
                error_code="INTERNAL_ERROR",
            )

    async def _execute_nl_query(
        self,
        session: AgentSession,
        query: AgentQuery,
    ) -> QueryResult:
        """Execute a natural language query."""
        # Use the knowledge query overlay/compiler if available
        if self.query_compiler:
            compiled = await self.query_compiler.compile(
                question=query.query_text,
                user_trust=self.TRUST_LEVEL_VALUES.get(session.trust_level, 1),
            )

            # Execute the compiled Cypher
            if self.db:
                async with self.db.session() as db_session:
                    result_data = await db_session.run(
                        compiled.cypher,
                        compiled.parameters,
                    )
                    records = [dict(r) for r in await result_data.data()]
            else:
                records = []

            # Apply trust filtering
            filtered_records = await self._filter_by_trust(session, records)

            # Synthesize answer
            answer = await self._synthesize_answer(query.query_text, filtered_records)

            return QueryResult(
                query_id=query.id,
                session_id=session.id,
                success=True,
                results=filtered_records[:query.max_results],
                total_count=len(filtered_records),
                generated_cypher=compiled.cypher,
                cypher_explanation=compiled.explanation,
                answer=answer,
                sources=self._extract_sources(filtered_records),
                tokens_used=len(query.query_text.split()) * 2,  # Estimate
            )

        # Fallback: simple keyword search
        return await self._execute_semantic_search(session, query)

    async def _execute_semantic_search(
        self,
        session: AgentSession,
        query: AgentQuery,
    ) -> QueryResult:
        """Execute a semantic similarity search."""
        results = []

        if self.capsule_repo:
            # Get embedding for query
            # In production, use embedding service
            capsules = await self.capsule_repo.search_by_text(
                text=query.query_text,
                limit=query.max_results * 2,  # Get extra for filtering
            )

            for capsule in capsules:
                # Trust filtering
                if not await self._can_access_capsule(session, capsule):
                    continue

                results.append({
                    "capsule_id": capsule.id,
                    "title": getattr(capsule, 'title', ''),
                    "type": capsule.type.value if hasattr(capsule.type, 'value') else str(capsule.type),
                    "content_preview": capsule.content[:500] if capsule.content else "",
                    "trust_level": capsule.trust_level,
                    "created_at": capsule.created_at.isoformat() if capsule.created_at else None,
                })

                if len(results) >= query.max_results:
                    break

        return QueryResult(
            query_id=query.id,
            session_id=session.id,
            success=True,
            results=results,
            total_count=len(results),
            sources=self._extract_sources(results),
        )

    async def _execute_graph_traverse(
        self,
        session: AgentSession,
        query: AgentQuery,
    ) -> QueryResult:
        """Execute a graph traversal query."""
        results = []

        # Parse traversal parameters from context
        start_node = query.context.get("start_node")
        relationship_types = query.context.get("relationship_types", [])
        max_depth = query.context.get("max_depth", 3)
        direction = query.context.get("direction", "both")

        if self.db and start_node:
            # Build traversal Cypher
            rel_pattern = "|".join(relationship_types) if relationship_types else "DERIVED_FROM|RELATED_TO"
            direction_pattern = {
                "out": f"-[r:{rel_pattern}*1..{max_depth}]->",
                "in": f"<-[r:{rel_pattern}*1..{max_depth}]-",
                "both": f"-[r:{rel_pattern}*1..{max_depth}]-",
            }.get(direction, f"-[r:{rel_pattern}*1..{max_depth}]-")

            cypher = f"""
            MATCH (start:Capsule {{id: $start_node}}){direction_pattern}(end:Capsule)
            RETURN DISTINCT end.id AS capsule_id,
                   end.type AS type,
                   end.title AS title,
                   end.trust_level AS trust_level,
                   length(r) AS distance
            ORDER BY distance
            LIMIT $limit
            """

            async with self.db.session() as db_session:
                result_data = await db_session.run(
                    cypher,
                    {"start_node": start_node, "limit": query.max_results * 2}
                )
                records = [dict(r) for r in await result_data.data()]

            # Filter by trust
            for record in records:
                if await self._can_access_by_trust_level(session, record.get("trust_level", 0)):
                    results.append(record)
                    if len(results) >= query.max_results:
                        break

        return QueryResult(
            query_id=query.id,
            session_id=session.id,
            success=True,
            results=results,
            total_count=len(results),
            generated_cypher=cypher if self.db else None,
        )

    async def _execute_direct_cypher(
        self,
        session: AgentSession,
        query: AgentQuery,
    ) -> QueryResult:
        """Execute a direct Cypher query (trusted agents only)."""
        # Only trusted+ agents can run direct Cypher
        if self.TRUST_LEVEL_VALUES.get(session.trust_level, 0) < self.TRUST_LEVEL_VALUES[AgentTrustLevel.TRUSTED]:
            return QueryResult(
                query_id=query.id,
                session_id=session.id,
                success=False,
                error="Direct Cypher queries require TRUSTED trust level",
                error_code="FORBIDDEN",
            )

        # Validate query is read-only (no CREATE, DELETE, SET, etc.)
        dangerous_keywords = ["CREATE", "DELETE", "SET", "REMOVE", "MERGE", "DROP"]
        query_upper = query.query_text.upper()
        for keyword in dangerous_keywords:
            if keyword in query_upper:
                return QueryResult(
                    query_id=query.id,
                    session_id=session.id,
                    success=False,
                    error=f"Write operations not allowed: {keyword}",
                    error_code="FORBIDDEN",
                )

        results = []
        if self.db:
            async with self.db.session() as db_session:
                result_data = await db_session.run(
                    query.query_text,
                    query.context.get("parameters", {}),
                )
                results = [dict(r) for r in await result_data.data()]

        return QueryResult(
            query_id=query.id,
            session_id=session.id,
            success=True,
            results=results[:query.max_results],
            total_count=len(results),
            generated_cypher=query.query_text,
        )

    async def _execute_aggregation(
        self,
        session: AgentSession,
        query: AgentQuery,
    ) -> QueryResult:
        """Execute an aggregation query."""
        # Parse aggregation type from query text
        aggregation_type = query.context.get("aggregation_type", "count")

        results = {}

        if self.db:
            if aggregation_type == "count_by_type":
                cypher = """
                MATCH (c:Capsule)
                RETURN c.type AS type, count(c) AS count
                ORDER BY count DESC
                """
            elif aggregation_type == "trust_distribution":
                cypher = """
                MATCH (c:Capsule)
                RETURN c.trust_level AS trust_level, count(c) AS count
                ORDER BY trust_level
                """
            elif aggregation_type == "recent_activity":
                cypher = """
                MATCH (c:Capsule)
                WHERE c.created_at > datetime() - duration('P7D')
                RETURN date(c.created_at) AS date, count(c) AS count
                ORDER BY date
                """
            else:
                cypher = "MATCH (c:Capsule) RETURN count(c) AS total"

            async with self.db.session() as db_session:
                result_data = await db_session.run(cypher)
                records = [dict(r) for r in await result_data.data()]
                results = {"data": records, "aggregation_type": aggregation_type}

        return QueryResult(
            query_id=query.id,
            session_id=session.id,
            success=True,
            results=[results],
            total_count=1,
            generated_cypher=cypher if self.db else None,
        )

    # =========================================================================
    # Capsule Creation
    # =========================================================================

    async def create_capsule(
        self,
        session: AgentSession,
        request: AgentCapsuleCreation,
    ) -> dict[str, Any]:
        """Create a capsule on behalf of an agent."""
        # Check capability
        if AgentCapability.CREATE_CAPSULES not in session.capabilities:
            raise ValueError("Agent does not have CREATE_CAPSULES capability")

        # Verify source capsules are accessible
        for source_id in request.source_capsule_ids:
            if self.capsule_repo:
                source = await self.capsule_repo.get(source_id)
                if source and not await self._can_access_capsule(session, source):
                    raise ValueError(f"Cannot derive from inaccessible capsule: {source_id}")

        # Create capsule through repository
        if self.capsule_repo:
            from forge.models.capsule import CapsuleType

            capsule = await self.capsule_repo.create(
                type=CapsuleType(request.capsule_type),
                content=request.content,
                creator_id=session.owner_user_id,
                source_ids=request.source_capsule_ids,
                metadata={
                    **request.metadata,
                    "created_by_agent": session.agent_id,
                    "agent_reasoning": request.reasoning,
                    "requires_approval": request.requires_approval,
                },
            )

            # Log access
            self._access_logs.append(CapsuleAccess(
                session_id=session.id,
                agent_id=session.agent_id,
                capsule_id=capsule.id,
                access_type=AccessType.WRITE,
                capsule_trust_level=capsule.trust_level,
                agent_trust_level=session.trust_level,
                access_granted=True,
            ))

            self._stats.capsules_created += 1

            return {
                "capsule_id": capsule.id,
                "status": "pending_approval" if request.requires_approval else "created",
            }

        return {"error": "Capsule repository not available"}

    # =========================================================================
    # Streaming Responses
    # =========================================================================

    async def stream_query(
        self,
        session: AgentSession,
        query: AgentQuery,
    ) -> AsyncIterator[StreamChunk]:
        """Stream query results as they become available."""
        chunk_id = 0

        # Start chunk
        yield StreamChunk(
            chunk_id=chunk_id,
            query_id=query.id,
            content_type="text",
            content="Processing query...",
            progress_percent=10,
        )
        chunk_id += 1

        # Execute query
        result = await self.execute_query(session, query)

        # Stream results
        for i, item in enumerate(result.results):
            yield StreamChunk(
                chunk_id=chunk_id,
                query_id=query.id,
                content_type="result",
                content=item,
                progress_percent=20 + int((i / max(len(result.results), 1)) * 60),
            )
            chunk_id += 1
            await asyncio.sleep(0.01)  # Small delay for streaming effect

        # Answer chunk
        if result.answer:
            yield StreamChunk(
                chunk_id=chunk_id,
                query_id=query.id,
                content_type="text",
                content=result.answer,
                progress_percent=90,
            )
            chunk_id += 1

        # Done chunk
        yield StreamChunk(
            chunk_id=chunk_id,
            query_id=query.id,
            content_type="done",
            content={
                "success": result.success,
                "total_count": result.total_count,
                "execution_time_ms": result.execution_time_ms,
            },
            is_final=True,
            progress_percent=100,
        )

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _get_required_capability(self, query_type: QueryType) -> AgentCapability | None:
        """Get required capability for a query type."""
        mapping = {
            QueryType.NATURAL_LANGUAGE: AgentCapability.QUERY_GRAPH,
            QueryType.SEMANTIC_SEARCH: AgentCapability.SEMANTIC_SEARCH,
            QueryType.GRAPH_TRAVERSE: AgentCapability.QUERY_GRAPH,
            QueryType.DIRECT_CYPHER: AgentCapability.QUERY_GRAPH,
            QueryType.AGGREGATION: AgentCapability.QUERY_GRAPH,
        }
        return mapping.get(query_type)

    def _get_cache_key(self, query: AgentQuery) -> str | None:
        """Generate cache key for a query."""
        if query.query_type == QueryType.DIRECT_CYPHER:
            return None  # Don't cache direct queries

        return hashlib.md5(
            f"{query.query_type.value}:{query.query_text}:{query.max_results}".encode()
        ).hexdigest()

    async def _filter_by_trust(
        self,
        session: AgentSession,
        records: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Filter records based on agent trust level."""
        trust_value = self.TRUST_LEVEL_VALUES.get(session.trust_level, 0)

        # Map trust level to capsule trust threshold
        # Untrusted agents can only see COMMUNITY+ capsules
        # Basic can see EMERGING+
        # Verified can see UNVERIFIED+
        # Trusted and System can see all

        min_capsule_trust = {
            AgentTrustLevel.UNTRUSTED: TrustLevel.COMMUNITY,
            AgentTrustLevel.BASIC: TrustLevel.EMERGING,
            AgentTrustLevel.VERIFIED: TrustLevel.UNVERIFIED,
            AgentTrustLevel.TRUSTED: TrustLevel.UNVERIFIED,
            AgentTrustLevel.SYSTEM: TrustLevel.UNVERIFIED,
        }.get(session.trust_level, TrustLevel.COMMUNITY)

        filtered = []
        for record in records:
            capsule_trust = record.get("trust_level", 0)
            if isinstance(capsule_trust, int) and capsule_trust >= min_capsule_trust.value:
                filtered.append(record)
            elif isinstance(capsule_trust, str):
                try:
                    trust_enum = TrustLevel[capsule_trust.upper()]
                    if trust_enum.value >= min_capsule_trust.value:
                        filtered.append(record)
                except (KeyError, AttributeError):
                    pass

        return filtered

    async def _can_access_capsule(self, session: AgentSession, capsule: Any) -> bool:
        """Check if agent can access a specific capsule."""
        # Check type restrictions
        if session.allowed_capsule_types:
            capsule_type = capsule.type.value if hasattr(capsule.type, 'value') else str(capsule.type)
            if capsule_type not in session.allowed_capsule_types:
                return False

        # Check trust level
        return await self._can_access_by_trust_level(session, capsule.trust_level)

    async def _can_access_by_trust_level(
        self,
        session: AgentSession,
        capsule_trust_level: int,
    ) -> bool:
        """Check if agent can access based on trust level."""
        trust_value = self.TRUST_LEVEL_VALUES.get(session.trust_level, 0)

        min_capsule_trust = {
            0: 3,  # UNTRUSTED: COMMUNITY+
            1: 2,  # BASIC: EMERGING+
            2: 1,  # VERIFIED: UNVERIFIED+
            3: 0,  # TRUSTED: all
            4: 0,  # SYSTEM: all
        }.get(trust_value, 3)

        return capsule_trust_level >= min_capsule_trust

    async def _synthesize_answer(
        self,
        question: str,
        results: list[dict[str, Any]],
    ) -> str:
        """Synthesize a natural language answer from results."""
        if not results:
            return "No relevant information found for your query."

        # In production, use LLM to synthesize
        # For now, create a simple summary
        count = len(results)
        types = set(r.get("type", "unknown") for r in results)

        answer = f"Found {count} relevant capsule(s) "
        if types:
            answer += f"of type(s): {', '.join(types)}. "

        # Add first result preview
        if results and "content_preview" in results[0]:
            answer += f"Top result: {results[0].get('content_preview', '')[:200]}..."

        return answer

    def _extract_sources(self, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Extract source citations from results."""
        sources = []
        for r in results:
            if "capsule_id" in r:
                sources.append({
                    "capsule_id": r["capsule_id"],
                    "title": r.get("title", ""),
                    "type": r.get("type", ""),
                })
        return sources

    # =========================================================================
    # Statistics
    # =========================================================================

    async def get_stats(self) -> GatewayStats:
        """Get gateway statistics."""
        self._stats.calculated_at = datetime.now(timezone.utc)
        self._stats.active_sessions = len([s for s in self._sessions.values() if s.is_active])

        if self._stats.queries_today > 0:
            self._stats.error_rate = self._stats.error_count / self._stats.queries_today

        return self._stats

    async def get_access_logs(
        self,
        session_id: str | None = None,
        limit: int = 100,
    ) -> list[CapsuleAccess]:
        """Get access logs, optionally filtered by session."""
        logs = self._access_logs
        if session_id:
            logs = [l for l in logs if l.session_id == session_id]
        return logs[-limit:]


# Singleton instance
_gateway_service: AgentGatewayService | None = None


async def get_gateway_service() -> AgentGatewayService:
    """Get or create the gateway service singleton."""
    global _gateway_service
    if _gateway_service is None:
        _gateway_service = AgentGatewayService()
    return _gateway_service
