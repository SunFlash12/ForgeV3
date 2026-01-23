"""
Ghost Council GAME SDK Integration

This module bridges the Ghost Council service with the Virtuals Protocol
GAME SDK, enabling council members to function as autonomous AI agents.

Each council member becomes a GAME agent with:
- Specialized workers for their domain expertise
- Functions for proposal analysis, voting, and deliberation
- Persistent memory for learning from past decisions
- Cross-council collaboration capabilities

The GAME framework enables more sophisticated reasoning by:
1. Using the Task Generator for high-level planning
2. Leveraging specialized workers for domain-specific analysis
3. Maintaining agent state across deliberations
4. Supporting multi-turn reasoning and collaboration
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from forge.models.governance import (
    GhostCouncilMember,
    GhostCouncilOpinion,
    GhostCouncilVote,
    PerspectiveAnalysis,
    PerspectiveType,
    Proposal,
    VoteChoice,
)
from forge.services.ghost_council import (
    DEFAULT_COUNCIL_MEMBERS,
    GhostCouncilConfig,
    GhostCouncilService,
)
from forge.virtuals.game.sdk_client import (
    FunctionDefinition,
    GAMEClientError,
    GAMESDKClient,
    GAMEWorker,
    get_game_client,
)
from forge.virtuals.models import (
    AgentGoals,
    AgentPersonality,
    ForgeAgent,
    ForgeAgentCreate,
    MemoryConfig,
)

logger = logging.getLogger(__name__)


# =============================================================================
# GAME FUNCTIONS FOR COUNCIL MEMBERS
# =============================================================================

def create_analyze_proposal_function(council_service: GhostCouncilService) -> FunctionDefinition:
    """Create the analyze_proposal function for council workers."""

    async def analyze_proposal(
        proposal_id: str,
        perspective: str,
        focus_areas: str = "",
    ) -> tuple[str, dict, dict]:
        """
        Analyze a proposal from a specific perspective.

        Returns:
            (status, result_dict, state_update)
        """
        try:
            # Get proposal details (would need to be passed via context/state)
            result = {
                "proposal_id": proposal_id,
                "perspective": perspective,
                "focus_areas": focus_areas.split(",") if focus_areas else [],
                "analysis_complete": True,
                "timestamp": datetime.now(UTC).isoformat(),
            }
            return ("DONE", result, {"last_analysis": result})
        except Exception as e:
            return ("FAILED", {"error": str(e)}, {})

    return FunctionDefinition(
        name="analyze_proposal",
        description="Analyze a governance proposal from a specific perspective (optimistic, balanced, or critical)",
        arguments=[
            {
                "name": "proposal_id",
                "type": "string",
                "description": "The ID of the proposal to analyze",
            },
            {
                "name": "perspective",
                "type": "string",
                "description": "The perspective to use: 'optimistic', 'balanced', or 'critical'",
            },
            {
                "name": "focus_areas",
                "type": "string",
                "description": "Comma-separated list of specific areas to focus on",
            },
        ],
        executable=analyze_proposal,
        returns_description="Analysis results including key points and assessment",
    )


def create_cast_vote_function() -> FunctionDefinition:
    """Create the cast_vote function for council workers."""

    async def cast_vote(
        proposal_id: str,
        vote: str,
        confidence: float,
        reasoning: str,
    ) -> tuple[str, dict, dict]:
        """
        Cast a vote on a proposal.

        Returns:
            (status, result_dict, state_update)
        """
        try:
            vote_choice = VoteChoice(vote.upper())
            result = {
                "proposal_id": proposal_id,
                "vote": vote_choice.value,
                "confidence": confidence,
                "reasoning": reasoning,
                "voted_at": datetime.now(UTC).isoformat(),
            }
            return ("DONE", result, {"last_vote": result})
        except ValueError:
            return ("FAILED", {"error": f"Invalid vote: {vote}"}, {})

    return FunctionDefinition(
        name="cast_vote",
        description="Cast a vote on a governance proposal",
        arguments=[
            {
                "name": "proposal_id",
                "type": "string",
                "description": "The ID of the proposal to vote on",
            },
            {
                "name": "vote",
                "type": "string",
                "description": "The vote choice: 'approve', 'reject', or 'abstain'",
            },
            {
                "name": "confidence",
                "type": "number",
                "description": "Confidence level 0.0-1.0",
            },
            {
                "name": "reasoning",
                "type": "string",
                "description": "Detailed reasoning for the vote",
            },
        ],
        executable=cast_vote,
        returns_description="Vote confirmation with timestamp",
    )


def create_request_clarification_function() -> FunctionDefinition:
    """Create function to request more information about a proposal."""

    async def request_clarification(
        proposal_id: str,
        questions: str,
    ) -> tuple[str, dict, dict]:
        """Request clarification on aspects of a proposal."""
        result = {
            "proposal_id": proposal_id,
            "questions": questions.split(";"),
            "status": "pending_response",
            "requested_at": datetime.now(UTC).isoformat(),
        }
        return ("PENDING", result, {"pending_clarification": result})

    return FunctionDefinition(
        name="request_clarification",
        description="Request clarification or additional information about a proposal",
        arguments=[
            {
                "name": "proposal_id",
                "type": "string",
                "description": "The proposal ID",
            },
            {
                "name": "questions",
                "type": "string",
                "description": "Semicolon-separated list of questions",
            },
        ],
        executable=request_clarification,
        returns_description="Clarification request status",
    )


def create_consult_colleague_function() -> FunctionDefinition:
    """Create function for council members to consult each other."""

    async def consult_colleague(
        colleague_id: str,
        topic: str,
        question: str,
    ) -> tuple[str, dict, dict]:
        """Consult another council member for their expertise."""
        result = {
            "colleague_id": colleague_id,
            "topic": topic,
            "question": question,
            "consultation_requested": True,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        return ("PENDING", result, {"pending_consultation": result})

    return FunctionDefinition(
        name="consult_colleague",
        description="Consult another Ghost Council member for their expertise on a specific topic",
        arguments=[
            {
                "name": "colleague_id",
                "type": "string",
                "description": "ID of the council member to consult (e.g., gc_security, gc_ethics)",
            },
            {
                "name": "topic",
                "type": "string",
                "description": "The topic or domain to discuss",
            },
            {
                "name": "question",
                "type": "string",
                "description": "The specific question or concern",
            },
        ],
        executable=consult_colleague,
        returns_description="Consultation request status",
    )


def create_search_precedents_function() -> FunctionDefinition:
    """Create function to search past decisions for precedents."""

    async def search_precedents(
        query: str,
        category: str = "",
        limit: int = 5,
    ) -> tuple[str, dict, dict]:
        """Search for relevant past decisions and precedents."""
        # This would integrate with the actual governance repository
        result = {
            "query": query,
            "category": category,
            "precedents_found": [],  # Would be populated from database
            "searched_at": datetime.now(UTC).isoformat(),
        }
        return ("DONE", result, {"last_search": result})

    return FunctionDefinition(
        name="search_precedents",
        description="Search past governance decisions for relevant precedents",
        arguments=[
            {
                "name": "query",
                "type": "string",
                "description": "Search query describing the precedent to find",
            },
            {
                "name": "category",
                "type": "string",
                "description": "Optional category filter (security, ethics, governance, etc.)",
            },
            {
                "name": "limit",
                "type": "number",
                "description": "Maximum number of precedents to return",
            },
        ],
        executable=search_precedents,
        returns_description="List of relevant past decisions",
    )


# =============================================================================
# COUNCIL MEMBER WORKERS
# =============================================================================

def create_council_member_worker(
    member: GhostCouncilMember,
    council_service: GhostCouncilService,
) -> GAMEWorker:
    """
    Create a GAME worker for a Ghost Council member.

    Each worker has access to:
    - Proposal analysis functions
    - Voting functions
    - Collaboration functions
    - Precedent search
    """
    # Define the functions available to this worker
    functions = [
        create_analyze_proposal_function(council_service),
        create_cast_vote_function(),
        create_request_clarification_function(),
        create_consult_colleague_function(),
        create_search_precedents_function(),
    ]

    # State function that tracks deliberation progress
    def get_worker_state(function_result: Any, current_state: dict) -> dict:
        new_state = current_state.copy()

        if function_result:
            result = function_result.get("result", {})
            if "last_analysis" in function_result.get("state_update", {}):
                analyses = new_state.get("analyses", [])
                analyses.append(result)
                new_state["analyses"] = analyses[-3:]  # Keep last 3
            if "last_vote" in function_result.get("state_update", {}):
                new_state["current_vote"] = result

        return new_state

    return GAMEWorker(
        worker_id=member.id,
        description=f"{member.name} - {member.role}: Expert in {member.domain}. {member.persona[:200]}...",
        functions=functions,
        get_state_fn=get_worker_state,
    )


# =============================================================================
# GAME-ENABLED GHOST COUNCIL SERVICE
# =============================================================================

class GAMEGhostCouncilService:
    """
    Ghost Council service enhanced with GAME SDK integration.

    This service manages Ghost Council members as autonomous GAME agents,
    enabling more sophisticated deliberation through:
    - Multi-turn reasoning loops
    - Cross-member collaboration
    - Persistent agent memory
    - Autonomous decision-making
    """

    def __init__(
        self,
        config: GhostCouncilConfig | None = None,
        council_members: list[GhostCouncilMember] | None = None,
    ):
        """Initialize the GAME-enabled Ghost Council."""
        self._config = config or GhostCouncilConfig()
        self._members = council_members or DEFAULT_COUNCIL_MEMBERS
        self._base_council = GhostCouncilService(config, council_members)

        # GAME SDK resources
        self._game_client: GAMESDKClient | None = None
        self._agent_registry: dict[str, ForgeAgent] = {}
        self._worker_registry: dict[str, GAMEWorker] = {}

        # Statistics
        self._stats = {
            "game_deliberations": 0,
            "fallback_deliberations": 0,
            "agent_interactions": 0,
        }

    async def initialize(self) -> None:
        """Initialize the GAME SDK client and register council member agents."""
        try:
            self._game_client = await get_game_client()
            logger.info("GAME SDK client initialized for Ghost Council")

            # Register each council member as a GAME agent
            for member in self._members:
                await self._register_council_agent(member)

        except GAMEClientError as e:
            logger.warning(
                f"Failed to initialize GAME SDK for Ghost Council: {e}. "
                "Falling back to standard LLM-based deliberation."
            )
            self._game_client = None

    async def _register_council_agent(self, member: GhostCouncilMember) -> None:
        """Register a council member as a GAME agent."""
        # Create the worker for this member
        worker = create_council_member_worker(member, self._base_council)
        self._worker_registry[member.id] = worker

        # Create agent specification
        create_request = ForgeAgentCreate(
            name=f"GhostCouncil_{member.name}",
            personality=AgentPersonality(
                bio=member.persona[:500],
                lore=[
                    f"Member of the Forge Ghost Council as {member.role}",
                    f"Domain expertise: {member.domain}",
                    f"Decision weight: {member.weight}",
                ],
                adjectives=["thoughtful", "analytical", "principled"],
                knowledge=[
                    "Governance processes and procedures",
                    f"Domain-specific knowledge in {member.domain}",
                    "Constitutional principles of the Forge system",
                ],
            ),
            goals=AgentGoals(
                primary_goal=f"Provide expert analysis and advice on governance proposals as the {member.role}",
                secondary_goals=[
                    "Ensure thorough tri-perspective analysis (optimistic, balanced, critical)",
                    "Collaborate with other council members when needed",
                    "Maintain consistency with past decisions and precedents",
                ],
            ),
            memory_config=MemoryConfig(
                short_term_window=10,
                long_term_enabled=True,
                summarization_enabled=True,
            ),
        )

        try:
            if self._game_client:
                agent = await self._game_client.create_agent(
                    create_request,
                    workers=[worker],
                )
                self._agent_registry[member.id] = agent
                logger.info(
                    f"Registered GAME agent for council member: {member.name}"
                )
        except GAMEClientError as e:
            logger.warning(f"Failed to register GAME agent for {member.name}: {e}")

    async def deliberate_proposal(
        self,
        proposal: Proposal,
        context: dict[str, Any] | None = None,
        constitutional_review: dict[str, Any] | None = None,
        use_game_agents: bool = True,
    ) -> GhostCouncilOpinion:
        """
        Have the Ghost Council deliberate on a proposal using GAME agents.

        If GAME SDK is not available or fails, falls back to standard
        LLM-based deliberation.

        Args:
            proposal: The governance proposal to review
            context: Additional context
            constitutional_review: Optional Constitutional AI review
            use_game_agents: Whether to attempt GAME-based deliberation

        Returns:
            Collective Ghost Council opinion
        """
        # Try GAME-based deliberation first
        if use_game_agents and self._game_client and self._agent_registry:
            try:
                opinion = await self._game_deliberate(
                    proposal, context, constitutional_review
                )
                self._stats["game_deliberations"] += 1
                return opinion
            except GAMEClientError as e:
                logger.warning(
                    f"GAME deliberation failed, falling back to LLM: {e}"
                )

        # Fall back to standard deliberation
        self._stats["fallback_deliberations"] += 1
        return await self._base_council.deliberate_proposal(
            proposal, context, constitutional_review
        )

    async def _game_deliberate(
        self,
        proposal: Proposal,
        context: dict[str, Any] | None,
        constitutional_review: dict[str, Any] | None,
    ) -> GhostCouncilOpinion:
        """
        Perform deliberation using GAME agents.

        Each agent runs its autonomous loop to:
        1. Analyze the proposal from multiple perspectives
        2. Search for relevant precedents
        3. Optionally consult other council members
        4. Cast their vote with reasoning
        """
        member_votes: list[GhostCouncilVote] = []

        # Build context string for agents
        context_str = f"""
PROPOSAL FOR REVIEW:
- ID: {proposal.id}
- Title: {proposal.title}
- Description: {proposal.description}
- Type: {proposal.type}
- Proposer: {proposal.proposer_id}
- Status: {proposal.status}

{"CONSTITUTIONAL REVIEW:" if constitutional_review else ""}
{constitutional_review if constitutional_review else ""}

Please analyze this proposal thoroughly using the tri-perspective protocol,
then cast your vote.
"""

        # Run each agent's deliberation in parallel
        deliberation_tasks = []
        for member in self._members:
            if member.id in self._agent_registry and member.id in self._worker_registry:
                task = self._run_agent_deliberation(
                    member,
                    self._agent_registry[member.id],
                    self._worker_registry[member.id],
                    context_str,
                )
                deliberation_tasks.append((member, task))

        # Gather results
        for member, task in deliberation_tasks:
            try:
                vote = await task
                member_votes.append(vote)
                self._stats["agent_interactions"] += 1
            except Exception as e:
                logger.error(f"Agent {member.name} deliberation failed: {e}")
                # Create abstain vote on failure
                member_votes.append(
                    GhostCouncilVote(
                        member_id=member.id,
                        member_name=member.name,
                        member_role=member.role,
                        vote=VoteChoice.ABSTAIN,
                        confidence=0.0,
                        reasoning=f"Deliberation failed: {e}",
                        weight=member.weight,
                        perspectives=[],
                    )
                )

        # Calculate consensus using base council's method
        consensus = self._base_council._calculate_consensus(member_votes)

        return GhostCouncilOpinion(
            proposal_id=proposal.id,
            deliberated_at=datetime.now(UTC),
            member_votes=member_votes,
            consensus_vote=consensus["vote"],
            consensus_strength=consensus["strength"],
            optimistic_summary=consensus.get("optimistic_summary", ""),
            balanced_summary=consensus.get("balanced_summary", ""),
            critical_summary=consensus.get("critical_summary", ""),
            key_points=consensus["key_points"],
            dissenting_opinions=consensus["dissenting"],
            final_recommendation=consensus["recommendation"],
            total_benefits_identified=consensus.get("total_benefits", 0),
            total_concerns_identified=consensus.get("total_concerns", 0),
        )

    async def _run_agent_deliberation(
        self,
        member: GhostCouncilMember,
        agent: ForgeAgent,
        worker: GAMEWorker,
        context: str,
    ) -> GhostCouncilVote:
        """
        Run a single agent's deliberation loop.

        The agent will autonomously:
        1. Analyze from optimistic perspective
        2. Analyze from balanced perspective
        3. Analyze from critical perspective
        4. Cast final vote
        """
        if not self._game_client:
            raise GAMEClientError("GAME client not initialized")

        # Run the agent loop
        results = await self._game_client.run_agent_loop(
            agent=agent,
            workers={member.id: worker},
            context=context,
            max_iterations=6,  # Enough for 3 perspectives + vote + buffer
            stop_condition=lambda r: r.get("function_name") == "cast_vote",
        )

        # Extract the vote from results
        vote_result = None
        perspectives = []

        for result in results:
            if result.get("function_name") == "cast_vote":
                vote_result = result.get("result", {})
            elif result.get("function_name") == "analyze_proposal":
                analysis = result.get("result", {})
                perspective_type = analysis.get("perspective", "balanced")
                perspectives.append(
                    PerspectiveAnalysis(
                        perspective=PerspectiveType(perspective_type.upper()),
                        analysis=result.get("reasoning", ""),
                        key_points=[],
                        confidence=0.7,
                    )
                )

        if vote_result:
            return GhostCouncilVote(
                member_id=member.id,
                member_name=member.name,
                member_role=member.role,
                vote=VoteChoice(vote_result.get("vote", "ABSTAIN")),
                confidence=vote_result.get("confidence", 0.5),
                reasoning=vote_result.get("reasoning", ""),
                weight=member.weight,
                perspectives=perspectives,
            )
        else:
            # No explicit vote found - default to abstain
            return GhostCouncilVote(
                member_id=member.id,
                member_name=member.name,
                member_role=member.role,
                vote=VoteChoice.ABSTAIN,
                confidence=0.3,
                reasoning="Agent completed analysis but did not cast explicit vote",
                weight=member.weight,
                perspectives=perspectives,
            )

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics."""
        base_stats = self._base_council.get_stats()
        return {
            **base_stats,
            "game_enabled": self._game_client is not None,
            "registered_agents": len(self._agent_registry),
            **self._stats,
        }

    async def close(self) -> None:
        """Cleanup resources."""
        if self._game_client:
            await self._game_client.close()


# Global service instance
_game_council_service: GAMEGhostCouncilService | None = None


async def get_game_council_service() -> GAMEGhostCouncilService:
    """
    Get the global GAME-enabled Ghost Council service.

    Initializes the service if not already done.
    """
    global _game_council_service
    if _game_council_service is None:
        _game_council_service = GAMEGhostCouncilService()
        await _game_council_service.initialize()
    return _game_council_service
