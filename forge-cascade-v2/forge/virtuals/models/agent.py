"""
Agent Models for GAME Framework Integration

This module defines models for representing AI agents within the
Virtuals Protocol GAME framework. These agents serve as tokenized
representations of Forge overlays and can operate autonomously.

The models support the full agent lifecycle from creation through
tokenization and graduation to sentient status.
"""

from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

from .base import (
    AgentStatus,
    TokenInfo,
    TokenizationStatus,
    VirtualsBaseModel,
    WalletInfo,
)


class AgentPersonality(BaseModel):
    """
    Defines the personality and behavioral characteristics of an agent.

    This configuration shapes how the agent interacts with users
    and other agents, forming the basis of the GAME framework's
    agent definition prompts.
    """
    name: str = Field(description="Display name of the agent")
    description: str = Field(
        max_length=2000,
        description="Detailed description of the agent's purpose and capabilities"
    )
    personality_traits: list[str] = Field(
        default_factory=list,
        description="List of personality traits (e.g., 'analytical', 'helpful')"
    )
    communication_style: str = Field(
        default="professional",
        description="Communication style (professional, casual, academic, etc.)"
    )
    expertise_domains: list[str] = Field(
        default_factory=list,
        description="Areas of expertise the agent specializes in"
    )
    response_guidelines: str = Field(
        default="",
        description="Guidelines for how the agent should respond to queries"
    )

    def to_game_prompt(self) -> str:
        """
        Convert personality to GAME framework agent definition prompt.

        The GAME framework uses natural language prompts to define
        agent behavior and decision-making patterns.
        """
        traits_str = ", ".join(self.personality_traits) if self.personality_traits else "helpful and professional"
        domains_str = ", ".join(self.expertise_domains) if self.expertise_domains else "general knowledge"

        return f"""Agent Name: {self.name}

Description: {self.description}

Personality: This agent exhibits the following traits: {traits_str}.
Communication style is {self.communication_style}.

Areas of Expertise: {domains_str}

Response Guidelines: {self.response_guidelines if self.response_guidelines else 'Provide accurate, helpful responses while maintaining professional demeanor.'}
"""


class WorkerDefinition(BaseModel):
    """
    Defines a worker (Low-Level Planner) for a GAME agent.

    Workers are specialized components that handle specific types
    of tasks. Each worker has access to a defined set of functions
    that it can execute.
    """
    id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique identifier for the worker"
    )
    name: str = Field(description="Worker name for identification")
    description: str = Field(
        description="Description of worker's purpose and capabilities"
    )
    function_names: list[str] = Field(
        default_factory=list,
        description="Names of functions this worker can execute"
    )
    state_schema: dict[str, Any] = Field(
        default_factory=dict,
        description="Schema for the worker's state object"
    )
    max_concurrent_tasks: int = Field(
        default=5,
        ge=1,
        description="Maximum tasks this worker can handle concurrently"
    )


class AgentGoals(BaseModel):
    """
    Defines the goals and objectives for an agent.

    Goals drive the High-Level Planner's decision making,
    determining what tasks the agent prioritizes.
    """
    primary_goal: str = Field(
        description="The agent's main objective"
    )
    secondary_goals: list[str] = Field(
        default_factory=list,
        description="Additional objectives to pursue"
    )
    constraints: list[str] = Field(
        default_factory=list,
        description="Constraints on agent behavior"
    )
    success_metrics: list[str] = Field(
        default_factory=list,
        description="Metrics used to evaluate agent performance"
    )


class AgentMemoryConfig(BaseModel):
    """
    Configuration for agent memory systems.

    Agents maintain both short-term (working) memory and
    long-term persistent memory for cross-session continuity.
    """
    enable_long_term_memory: bool = Field(
        default=True,
        description="Enable persistent long-term memory"
    )
    memory_retention_days: int = Field(
        default=365,
        description="Days to retain long-term memories"
    )
    max_working_memory_items: int = Field(
        default=100,
        description="Maximum items in working memory"
    )
    enable_cross_platform_sync: bool = Field(
        default=True,
        description="Sync memory across platforms (Telegram, Twitter, etc.)"
    )
    vector_embedding_model: str = Field(
        default="text-embedding-3-small",
        description="Model used for memory embeddings"
    )


class ForgeAgentCreate(BaseModel):
    """
    Schema for creating a new Forge agent on Virtuals Protocol.

    This represents the creation request for tokenizing a Forge
    overlay or creating a standalone knowledge agent.
    """
    # Core Identity
    name: str = Field(
        min_length=3,
        max_length=64,
        description="Agent name (used for token symbol derivation)"
    )
    personality: AgentPersonality
    goals: AgentGoals

    # Forge Integration
    forge_overlay_id: str | None = Field(
        default=None,
        description="ID of the Forge overlay this agent represents"
    )
    forge_capsule_ids: list[str] = Field(
        default_factory=list,
        description="IDs of Forge capsules this agent has access to"
    )

    # Workers Configuration
    workers: list[WorkerDefinition] = Field(
        default_factory=list,
        description="Worker definitions for task execution"
    )

    # Memory Configuration
    memory_config: AgentMemoryConfig = Field(
        default_factory=AgentMemoryConfig
    )

    # Tokenization Options
    enable_tokenization: bool = Field(
        default=False,
        description="Whether to tokenize this agent (opt-in)"
    )
    token_symbol: str | None = Field(
        default=None,
        max_length=10,
        description="Token symbol if tokenizing (e.g., 'FRGSEC')"
    )
    initial_virtual_stake: float = Field(
        default=100.0,
        ge=100.0,
        description="Initial VIRTUAL stake (minimum 100)"
    )

    # Chain Configuration
    primary_chain: str = Field(
        default="base",
        description="Primary blockchain for deployment"
    )

    @field_validator('token_symbol')
    @classmethod
    def validate_symbol(cls, v: str | None) -> str | None:
        """Ensure token symbol is uppercase and valid."""
        if v is not None:
            v = v.upper()
            if not v.isalnum():
                raise ValueError('Token symbol must be alphanumeric')
        return v


class ForgeAgent(VirtualsBaseModel):
    """
    Complete representation of a Forge agent on Virtuals Protocol.

    This model represents the full state of an agent including
    its configuration, tokenization status, and operational metrics.
    """
    # Core Identity
    name: str
    personality: AgentPersonality
    goals: AgentGoals
    status: AgentStatus = Field(default=AgentStatus.PROTOTYPE)

    # Forge Integration
    forge_overlay_id: str | None = None
    forge_capsule_ids: list[str] = Field(default_factory=list)

    # Workers
    workers: list[WorkerDefinition] = Field(default_factory=list)

    # Memory
    memory_config: AgentMemoryConfig = Field(default_factory=AgentMemoryConfig)

    # Virtuals Protocol Integration
    game_agent_id: str | None = Field(
        default=None,
        description="ID assigned by GAME framework"
    )
    api_access_token: str | None = Field(
        default=None,
        description="Current API access token (rotates)"
    )

    # Blockchain State
    primary_chain: str = Field(default="base")
    wallets: dict[str, WalletInfo] = Field(
        default_factory=dict,
        description="Wallets by chain (e.g., {'base': WalletInfo(...)})"
    )

    # Tokenization State
    tokenization_status: TokenizationStatus = Field(
        default=TokenizationStatus.NOT_TOKENIZED
    )
    token_info: TokenInfo | None = None

    # NFT State (ERC-721 + ERC-6551 TBA)
    nft_token_id: str | None = Field(
        default=None,
        description="Agent NFT token ID"
    )
    token_bound_account: str | None = Field(
        default=None,
        description="ERC-6551 token-bound account address"
    )

    # Operational Metrics
    total_queries_handled: int = Field(default=0)
    total_revenue_generated: float = Field(default=0.0)
    total_tasks_completed: int = Field(default=0)
    average_response_time_ms: float = Field(default=0.0)
    trust_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Trust score based on performance"
    )

    # Activity Tracking
    last_active_at: datetime | None = None
    total_active_hours: float = Field(default=0.0)

    def is_operational(self) -> bool:
        """Check if agent is in an operational state."""
        return self.status in [AgentStatus.PROTOTYPE, AgentStatus.SENTIENT]

    def is_tokenized(self) -> bool:
        """Check if agent has been tokenized."""
        return self.tokenization_status in [
            TokenizationStatus.BONDING,
            TokenizationStatus.GRADUATED,
            TokenizationStatus.BRIDGED,
        ]

    def get_wallet(self, chain: str) -> WalletInfo | None:
        """Get wallet for a specific chain."""
        return self.wallets.get(chain)

    def get_primary_wallet(self) -> WalletInfo | None:
        """Get the primary chain wallet."""
        return self.wallets.get(self.primary_chain)


class AgentUpdate(BaseModel):
    """Schema for updating an existing agent."""
    personality: AgentPersonality | None = None
    goals: AgentGoals | None = None
    workers: list[WorkerDefinition] | None = None
    memory_config: AgentMemoryConfig | None = None
    forge_capsule_ids: list[str] | None = None

    # Cannot change these after creation
    # - name
    # - forge_overlay_id
    # - tokenization settings


class AgentStats(BaseModel):
    """Aggregated statistics for an agent."""
    agent_id: str
    period_start: datetime
    period_end: datetime
    queries_handled: int = 0
    tasks_completed: int = 0
    revenue_generated_virtual: float = 0.0
    average_response_time_ms: float = 0.0
    error_rate: float = 0.0
    unique_users_served: int = 0
    acp_jobs_completed: int = 0
    acp_jobs_as_provider: int = 0
    acp_jobs_as_buyer: int = 0


class AgentListResponse(BaseModel):
    """Response model for listing agents."""
    agents: list[ForgeAgent]
    total: int
    page: int = 1
    per_page: int = 20
    has_more: bool = False
