"""
Tokenization Package for Forge Entities

This package provides opt-in tokenization capabilities for Forge assets
using Virtuals Protocol's tokenization infrastructure.

Tokenization transforms Forge entities (capsules, overlays, agents) into
revenue-generating blockchain tokens with governance rights and cross-chain
capabilities.

Key Features:
- Bonding curve price discovery
- Automatic graduation to Uniswap liquidity
- Revenue sharing with buyback-burn mechanics
- Token holder governance
- Cross-chain bridging via Wormhole

Example Usage:
    from forge.virtuals.tokenization import (
        get_tokenization_service,
        TokenizationRequest,
    )

    async def tokenize_capsule_collection():
        service = await get_tokenization_service(entity_repo, contrib_repo, proposal_repo)

        # Request tokenization
        entity = await service.request_tokenization(
            TokenizationRequest(
                entity_type="capsule_collection",
                entity_id="collection_123",
                token_name="Forge Q3 Strategy Knowledge",
                token_symbol="FRGQ3",
                initial_stake_virtual=100.0,
            )
        )

        # Entity starts in bonding curve phase
        print(f"Progress: {entity.token_info.bonding_curve_progress:.1%}")
"""

from .service import (
    GRADUATION_THRESHOLDS,
    AlreadyTokenizedError,
    InsufficientStakeError,
    TokenizationService,
    TokenizationServiceError,
    get_tokenization_service,
)

__all__ = [
    "TokenizationService",
    "TokenizationServiceError",
    "InsufficientStakeError",
    "AlreadyTokenizedError",
    "get_tokenization_service",
    "GRADUATION_THRESHOLDS",
]
