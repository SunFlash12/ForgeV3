"""
Cross-Chain Bridge Module

This module provides bridging functionality for VIRTUAL tokens between
Base, Ethereum, and Solana networks using the Wormhole protocol.
"""

from .service import (
    BridgeRequest,
    BridgeRoute,
    BridgeService,
    BridgeStatus,
    get_bridge_service,
)

__all__ = [
    "BridgeService",
    "BridgeRequest",
    "BridgeStatus",
    "BridgeRoute",
    "get_bridge_service",
]
