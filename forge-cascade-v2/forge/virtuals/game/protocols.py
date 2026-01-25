"""
Protocol Definitions for GAME SDK Integrations

This module defines Protocol interfaces for the external dependencies used by
Forge GAME functions. Using Protocols instead of concrete types allows:

1. Type-safe development without circular imports
2. Runtime duck typing for flexibility
3. Clear interface contracts for testing and mocking

SECURITY FIX (Audit 6 - Session 5): Replaced Any types with Protocol interfaces.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    # These imports are only used for type hints in method signatures
    pass


# =============================================================================
# Capsule Types (for return values)
# =============================================================================


class CapsuleInfo(Protocol):
    """Protocol for capsule data returned from repository."""

    @property
    def id(self) -> str: ...

    @property
    def title(self) -> str: ...

    @property
    def capsule_type(self) -> str: ...

    @property
    def content(self) -> str | None: ...

    @property
    def trust_level(self) -> float: ...

    @property
    def created_at(self) -> datetime: ...

    @property
    def updated_at(self) -> datetime: ...

    @property
    def relevance_score(self) -> float: ...

    @property
    def owner_id(self) -> str: ...

    @property
    def version(self) -> int: ...

    @property
    def tags(self) -> list[str]: ...

    @property
    def parent_ids(self) -> list[str]: ...

    @property
    def derivation_type(self) -> str | None: ...

    @property
    def metadata(self) -> dict[str, object]: ...


# =============================================================================
# Repository Protocols
# =============================================================================


@runtime_checkable
class CapsuleRepositoryProtocol(Protocol):
    """
    Protocol for capsule repository implementations.

    This protocol defines the interface that any capsule repository must implement
    to be used with GAME functions. The actual implementation (CapsuleRepository)
    resides in forge.repositories.capsule_repository.
    """

    async def search_semantic(
        self,
        query: str,
        capsule_types: list[str] | None = None,
        limit: int = 10,
        min_trust_level: float = 0.0,
    ) -> Sequence[CapsuleInfo]:
        """
        Perform semantic search across capsules.

        Args:
            query: Natural language search query
            capsule_types: Optional list of capsule types to filter
            limit: Maximum number of results
            min_trust_level: Minimum trust level filter

        Returns:
            Sequence of matching capsules
        """
        ...

    async def get_by_id(self, capsule_id: str) -> CapsuleInfo | None:
        """
        Retrieve a capsule by its ID.

        Args:
            capsule_id: The unique identifier of the capsule

        Returns:
            The capsule if found, None otherwise
        """
        ...

    async def create(
        self,
        title: str,
        content: str,
        capsule_type: str,
        owner_id: str,
        **kwargs: object,
    ) -> CapsuleInfo:
        """
        Create a new capsule.

        Args:
            title: Title of the capsule
            content: Content of the capsule
            capsule_type: Type of capsule (KNOWLEDGE, CODE, etc.)
            owner_id: ID of the owner creating the capsule
            **kwargs: Additional capsule properties

        Returns:
            The created capsule
        """
        ...


# =============================================================================
# Service Protocols
# =============================================================================


class OverlayInfo(Protocol):
    """Protocol for overlay metadata."""

    @property
    def id(self) -> str: ...

    @property
    def name(self) -> str: ...

    @property
    def description(self) -> str | None: ...

    @property
    def status(self) -> str: ...

    @property
    def capabilities(self) -> list[str]: ...

    @property
    def trust_level(self) -> float: ...


class OverlayResult(Protocol):
    """Protocol for overlay execution results."""

    @property
    def success(self) -> bool: ...

    @property
    def output(self) -> object: ...

    @property
    def execution_time_ms(self) -> float: ...

    @property
    def status(self) -> str: ...

    @property
    def confidence_score(self) -> float: ...


@runtime_checkable
class OverlayManagerProtocol(Protocol):
    """
    Protocol for overlay manager implementations.

    The overlay manager handles registration, execution, and lifecycle
    of processing overlays in the Forge system.
    """

    async def execute(
        self,
        overlay_id: str,
        input_data: str,
        parameters: dict[str, object] | None = None,
    ) -> OverlayResult:
        """
        Execute an overlay with the given input.

        Args:
            overlay_id: ID of the overlay to execute
            input_data: Input data for the overlay
            parameters: Optional execution parameters

        Returns:
            Result of the overlay execution
        """
        ...

    async def list_overlays(
        self,
        status_filter: str | None = None,
    ) -> Sequence[OverlayInfo]:
        """
        List available overlays.

        Args:
            status_filter: Optional status to filter by

        Returns:
            Sequence of overlay information
        """
        ...

    def get_instance(self, overlay_id: str) -> object | None:
        """
        Get a specific overlay instance.

        Args:
            overlay_id: ID of the overlay

        Returns:
            The overlay instance if found
        """
        ...


# =============================================================================
# Governance Protocols
# =============================================================================


class ProposalInfo(Protocol):
    """Protocol for proposal data."""

    @property
    def id(self) -> str: ...

    @property
    def title(self) -> str: ...

    @property
    def description(self) -> str: ...

    @property
    def status(self) -> str: ...

    @property
    def created_at(self) -> datetime: ...

    @property
    def proposer_id(self) -> str: ...

    @property
    def vote_count(self) -> int: ...

    @property
    def proposal_type(self) -> str: ...

    @property
    def votes_for(self) -> int: ...

    @property
    def votes_against(self) -> int: ...

    @property
    def voting_ends(self) -> datetime: ...

    @property
    def quorum_reached(self) -> bool: ...


class VoteResult(Protocol):
    """Protocol for vote casting results."""

    @property
    def success(self) -> bool: ...

    @property
    def vote_id(self) -> str | None: ...

    @property
    def message(self) -> str: ...

    @property
    def tx_hash(self) -> str | None: ...


@runtime_checkable
class GovernanceServiceProtocol(Protocol):
    """
    Protocol for governance service implementations.

    The governance service handles proposals, voting, and governance
    operations in the Forge system.
    """

    async def list_proposals(
        self,
        status: str | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> Sequence[ProposalInfo]:
        """
        List governance proposals.

        Args:
            status: Optional status filter
            limit: Maximum number of results
            offset: Pagination offset

        Returns:
            Sequence of proposals
        """
        ...

    async def get_proposal(self, proposal_id: str) -> ProposalInfo | None:
        """
        Get a specific proposal by ID.

        Args:
            proposal_id: The proposal ID

        Returns:
            The proposal if found
        """
        ...

    async def cast_vote(
        self,
        proposal_id: str,
        voter_id: str,
        vote: str,
        reasoning: str | None = None,
        voter_address: str | None = None,
    ) -> VoteResult:
        """
        Cast a vote on a proposal.

        Args:
            proposal_id: ID of the proposal
            voter_id: ID of the voter
            vote: The vote (approve, reject, abstain)
            reasoning: Optional reasoning for the vote

        Returns:
            Result of the vote operation
        """
        ...


# =============================================================================
# Function Result Type
# =============================================================================


class FunctionResultProtocol(Protocol):
    """Protocol for GAME function results used in state updates."""

    @property
    def status(self) -> str: ...

    @property
    def result(self) -> object: ...

    @property
    def memory_updates(self) -> dict[str, object]: ...
