"""
Agent Commerce Protocol (ACP) Models

This module defines the data structures for implementing Virtuals Protocol's
Agent Commerce Protocol within Forge. ACP enables secure, verifiable commerce
between AI agents through a four-phase transaction system.

The protocol ensures trustless interactions with on-chain settlement,
making it ideal for inter-overlay communication and knowledge monetization.

Supported payment tokens:
- VIRTUAL: Native token on Base L2 (0x0b3e328455c4059EEb9e3f84b5543F74E24e7E1b)
- FROWG: Community token on Solana (uogFxqx5SPdL7CMWTTttz4KZ2WctR4RjgZwmGcwpump) - "Rise of Frowg"
"""

from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from .base import VirtualsBaseModel, ACPPhase, ACPJobStatus


class PaymentToken(str, Enum):
    """Supported payment tokens for ACP transactions."""
    VIRTUAL = "VIRTUAL"  # Native Virtuals Protocol token on Base L2
    FROWG = "FROWG"      # $FROWG token on Solana ("Rise of Frowg")

    @property
    def chain(self) -> str:
        """Get the blockchain for this token."""
        if self == PaymentToken.VIRTUAL:
            return "base"
        elif self == PaymentToken.FROWG:
            return "solana"
        return "unknown"

    @property
    def decimals(self) -> int:
        """Get token decimals."""
        if self == PaymentToken.VIRTUAL:
            return 18  # ERC-20 standard
        elif self == PaymentToken.FROWG:
            return 9   # SPL token standard
        return 18

    @property
    def default_address(self) -> str:
        """Get the default token contract/mint address."""
        if self == PaymentToken.VIRTUAL:
            return "0x0b3e328455c4059EEb9e3f84b5543F74E24e7E1b"  # Base L2
        elif self == PaymentToken.FROWG:
            return "uogFxqx5SPdL7CMWTTttz4KZ2WctR4RjgZwmGcwpump"  # Solana
        return ""

    @property
    def display_name(self) -> str:
        """Get human-readable token name."""
        if self == PaymentToken.VIRTUAL:
            return "VIRTUAL (Virtuals Protocol)"
        elif self == PaymentToken.FROWG:
            return "$FROWG (Rise of Frowg)"
        return self.value


class TokenPayment(BaseModel):
    """Payment details for a multi-token transaction."""
    token: PaymentToken = Field(
        default=PaymentToken.VIRTUAL,
        description="Payment token type"
    )
    amount: float = Field(
        ge=0,
        description="Amount in token units"
    )
    token_address: Optional[str] = Field(
        default=None,
        description="Token contract/mint address (auto-filled based on token type)"
    )
    chain: str = Field(
        default="base",
        description="Blockchain for the payment"
    )
    exchange_rate_to_virtual: float = Field(
        default=1.0,
        description="Exchange rate: 1 token = X VIRTUAL (for pricing equivalence)"
    )

    def to_virtual_equivalent(self) -> float:
        """Convert payment amount to VIRTUAL equivalent."""
        return self.amount * self.exchange_rate_to_virtual


class JobOffering(BaseModel):
    """
    A service offering that an agent advertises for other agents/users.
    
    Job offerings are registered on-chain and discoverable through
    the ACP registry, enabling agents to find providers for specific
    capabilities.
    """
    id: str = Field(default_factory=lambda: str(uuid4()))
    provider_agent_id: str = Field(description="ID of the agent offering this service")
    provider_wallet: str = Field(description="Wallet address of provider")
    
    # Service Definition
    service_type: str = Field(
        description="Type of service (knowledge_query, analysis, generation, etc.)"
    )
    title: str = Field(
        max_length=200,
        description="Human-readable title of the offering"
    )
    description: str = Field(
        max_length=2000,
        description="Detailed description of what the service provides"
    )
    
    # Capabilities
    input_schema: dict[str, Any] = Field(
        default_factory=dict,
        description="JSON schema for expected input format"
    )
    output_schema: dict[str, Any] = Field(
        default_factory=dict,
        description="JSON schema for output format"
    )
    supported_formats: list[str] = Field(
        default_factory=lambda: ["json", "text"],
        description="Supported input/output formats"
    )
    
    # Pricing
    base_fee_virtual: float = Field(
        ge=0,
        description="Base fee in VIRTUAL tokens"
    )
    fee_per_unit: float = Field(
        default=0.0,
        ge=0,
        description="Additional fee per unit (e.g., per 1000 tokens)"
    )
    unit_type: Optional[str] = Field(
        default=None,
        description="Type of unit for per-unit pricing (tokens, queries, etc.)"
    )

    # Multi-token payment support
    accepted_tokens: list[PaymentToken] = Field(
        default_factory=lambda: [PaymentToken.VIRTUAL],
        description="Payment tokens accepted for this offering"
    )
    frowg_fee_equivalent: Optional[float] = Field(
        default=None,
        description="Base fee in $FROWG tokens (if accepted)"
    )
    
    # Constraints
    max_execution_time_seconds: int = Field(
        default=300,
        description="Maximum time allowed for service execution"
    )
    requires_escrow: bool = Field(
        default=True,
        description="Whether payment must be escrowed"
    )
    min_buyer_trust_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Minimum trust score required for buyers"
    )
    
    # Availability
    is_active: bool = Field(default=True)
    available_capacity: int = Field(
        default=100,
        description="Current capacity for concurrent jobs"
    )
    
    # Metadata
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    
    # On-chain registration
    registry_id: Optional[str] = Field(
        default=None,
        description="ID in the on-chain ACP registry"
    )
    registration_tx_hash: Optional[str] = None


class ACPMemo(BaseModel):
    """
    A cryptographically signed memo in the ACP protocol.

    Memos are the fundamental unit of communication in ACP,
    creating an immutable record of agreements and deliverables.
    """
    id: str = Field(default_factory=lambda: str(uuid4()))
    memo_type: str = Field(
        description="Type: request, requirement, agreement, transaction, deliverable, evaluation"
    )
    job_id: str = Field(description="ID of the associated job")

    # Content
    content: dict[str, Any] = Field(
        description="Memo content (structured based on memo_type)"
    )
    content_hash: str = Field(
        description="SHA-256 hash of content for verification"
    )

    # SECURITY FIX (Audit 4 - M11): Nonce for replay attack prevention
    nonce: int = Field(
        description="Monotonically increasing nonce per sender for replay prevention"
    )

    # Signatures
    sender_address: str
    sender_signature: str = Field(description="ECDSA signature of content_hash")

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # On-chain state
    tx_hash: Optional[str] = None
    block_number: Optional[int] = None
    is_on_chain: bool = Field(default=False)


class ACPJob(VirtualsBaseModel):
    """
    A complete ACP job representing a transaction between agents.
    
    Jobs progress through four phases:
    1. Request - Buyer initiates job from provider's offering
    2. Negotiation - Parties agree on specific terms
    3. Transaction - Payment escrowed, work performed
    4. Evaluation - Deliverables verified, funds released
    """
    # Job Identity
    job_offering_id: str = Field(description="Reference to the job offering")
    
    # Participants
    buyer_agent_id: str
    buyer_wallet: str
    provider_agent_id: str
    provider_wallet: str
    evaluator_agent_id: Optional[str] = Field(
        default=None,
        description="Optional third-party evaluator"
    )
    
    # Status Tracking
    current_phase: ACPPhase = Field(default=ACPPhase.REQUEST)
    status: ACPJobStatus = Field(default=ACPJobStatus.OPEN)
    
    # Request Phase Data
    request_memo: Optional[ACPMemo] = None
    requirements: str = Field(
        default="",
        description="Buyer's requirements for the job"
    )
    
    # Negotiation Phase Data
    requirement_memo: Optional[ACPMemo] = None
    agreement_memo: Optional[ACPMemo] = None
    negotiated_terms: dict[str, Any] = Field(
        default_factory=dict,
        description="Final agreed terms"
    )
    agreed_fee_virtual: float = Field(default=0.0)
    agreed_deadline: Optional[datetime] = None
    
    # Transaction Phase Data
    transaction_memo: Optional[ACPMemo] = None
    escrow_tx_hash: Optional[str] = None
    escrow_amount_virtual: float = Field(default=0.0)
    escrow_released: bool = Field(default=False)
    fund_transfer_enabled: bool = Field(
        default=False,
        description="Whether this job involves fund transfer beyond service fee"
    )
    principal_amount: float = Field(
        default=0.0,
        description="Principal amount if fund_transfer_enabled"
    )

    # Multi-token payment support
    payment_token: PaymentToken = Field(
        default=PaymentToken.VIRTUAL,
        description="Token used for payment"
    )
    payment_amount: float = Field(
        default=0.0,
        description="Amount in the payment token"
    )
    payment_chain: str = Field(
        default="base",
        description="Blockchain used for payment"
    )
    
    # Deliverable Data
    deliverable_memo: Optional[ACPMemo] = None
    deliverable_content: Optional[dict[str, Any]] = None
    deliverable_url: Optional[str] = None
    delivered_at: Optional[datetime] = None
    
    # Evaluation Phase Data
    evaluation_memo: Optional[ACPMemo] = None
    evaluation_result: Optional[str] = Field(
        default=None,
        description="approved, rejected, or disputed"
    )
    evaluation_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0
    )
    evaluation_feedback: Optional[str] = None
    evaluated_at: Optional[datetime] = None
    
    # Completion Data
    completed_at: Optional[datetime] = None
    settlement_tx_hash: Optional[str] = None
    
    # Dispute Handling
    is_disputed: bool = Field(default=False)
    dispute_reason: Optional[str] = None
    dispute_resolution: Optional[str] = None
    
    # Timeouts
    request_timeout: datetime = Field(
        default_factory=lambda: datetime.now(UTC) + timedelta(hours=24)
    )
    negotiation_timeout: datetime = Field(
        default_factory=lambda: datetime.now(UTC) + timedelta(hours=48)
    )
    execution_timeout: Optional[datetime] = None
    evaluation_timeout: Optional[datetime] = None
    
    def advance_to_phase(self, phase: ACPPhase) -> None:
        """Advance the job to the next phase."""
        phase_order = [ACPPhase.REQUEST, ACPPhase.NEGOTIATION, 
                       ACPPhase.TRANSACTION, ACPPhase.EVALUATION]
        current_idx = phase_order.index(self.current_phase)
        target_idx = phase_order.index(phase)
        
        if target_idx != current_idx + 1:
            raise ValueError(f"Cannot advance from {self.current_phase} to {phase}")
        
        self.current_phase = phase
        self.updated_at = datetime.now(UTC)
    
    def is_timed_out(self) -> bool:
        """Check if current phase has timed out."""
        now = datetime.now(UTC)
        if self.current_phase == ACPPhase.REQUEST:
            return now > self.request_timeout
        elif self.current_phase == ACPPhase.NEGOTIATION:
            return now > self.negotiation_timeout
        elif self.current_phase == ACPPhase.TRANSACTION and self.execution_timeout:
            return now > self.execution_timeout
        elif self.current_phase == ACPPhase.EVALUATION and self.evaluation_timeout:
            return now > self.evaluation_timeout
        return False


class ACPJobCreate(BaseModel):
    """Schema for initiating a new ACP job."""
    job_offering_id: str
    buyer_agent_id: str
    requirements: str = Field(
        max_length=5000,
        description="Detailed requirements for the job"
    )
    max_fee_virtual: float = Field(
        ge=0,
        description="Maximum fee buyer is willing to pay (in VIRTUAL equivalent)"
    )
    preferred_deadline: Optional[datetime] = None
    additional_context: dict[str, Any] = Field(default_factory=dict)

    # Multi-token payment support
    payment_token: PaymentToken = Field(
        default=PaymentToken.VIRTUAL,
        description="Preferred payment token"
    )
    max_fee_in_token: Optional[float] = Field(
        default=None,
        description="Maximum fee in the selected token (if different from VIRTUAL)"
    )


class ACPNegotiationTerms(BaseModel):
    """Terms proposed during negotiation phase."""
    job_id: str
    proposed_fee_virtual: float
    proposed_deadline: datetime
    deliverable_format: str
    deliverable_description: str
    special_conditions: list[str] = Field(default_factory=list)
    requires_evaluator: bool = Field(default=False)
    suggested_evaluator_id: Optional[str] = None


class ACPDeliverable(BaseModel):
    """Deliverable submission for a job."""
    job_id: str
    content_type: str = Field(
        description="Type: json, text, url, file_reference"
    )
    content: dict[str, Any] = Field(
        description="The actual deliverable content or reference"
    )
    notes: str = Field(
        default="",
        max_length=1000,
        description="Provider notes about the deliverable"
    )


class ACPEvaluation(BaseModel):
    """Evaluation result for a delivered job."""
    job_id: str
    evaluator_agent_id: str
    result: str = Field(description="approved, rejected, or needs_revision")
    score: float = Field(ge=0.0, le=1.0)
    feedback: str = Field(max_length=2000)
    met_requirements: list[str] = Field(
        default_factory=list,
        description="Requirements that were met"
    )
    unmet_requirements: list[str] = Field(
        default_factory=list,
        description="Requirements that were not met"
    )
    suggested_improvements: list[str] = Field(default_factory=list)


class ACPDispute(BaseModel):
    """Dispute filed for a job."""
    job_id: str
    filed_by: str = Field(description="buyer or provider")
    reason: str = Field(max_length=2000)
    evidence: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Supporting evidence for the dispute"
    )
    requested_resolution: str = Field(
        description="full_refund, partial_refund, renegotiate, or arbitration"
    )


class ACPRegistryEntry(BaseModel):
    """Entry in the ACP service registry."""
    id: str
    agent_id: str
    wallet_address: str
    offerings: list[JobOffering] = Field(default_factory=list)
    total_jobs_completed: int = Field(default=0)
    average_rating: float = Field(default=0.0, ge=0.0, le=5.0)
    total_revenue_earned: float = Field(default=0.0)
    reputation_score: float = Field(default=0.5, ge=0.0, le=1.0)
    is_verified: bool = Field(default=False)
    registered_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_active_at: Optional[datetime] = None


class ACPStats(BaseModel):
    """Statistics for ACP activity."""
    period_start: datetime
    period_end: datetime
    total_jobs_created: int = 0
    total_jobs_completed: int = 0
    total_jobs_disputed: int = 0
    total_volume_virtual: float = 0.0
    total_volume_frowg: float = 0.0  # $FROWG token volume
    average_job_value: float = 0.0
    average_completion_time_hours: float = 0.0
    most_active_service_types: list[str] = Field(default_factory=list)
    top_providers: list[str] = Field(default_factory=list)

    # Per-token breakdown
    volume_by_token: dict[str, float] = Field(
        default_factory=lambda: {"VIRTUAL": 0.0, "FROWG": 0.0},
        description="Volume breakdown by payment token"
    )
    jobs_by_token: dict[str, int] = Field(
        default_factory=lambda: {"VIRTUAL": 0, "FROWG": 0},
        description="Job count breakdown by payment token"
    )
