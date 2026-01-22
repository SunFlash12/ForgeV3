"""
Multi-Chain Client Package

This package provides blockchain client implementations for interacting
with multiple chains supported by Virtuals Protocol:

- Base (Primary): Main deployment chain for Virtuals Protocol
- Ethereum: Bridge and cross-chain operations
- Solana: Alternative deployment with lower fees

Usage:
    from forge.virtuals.chains import get_chain_manager, ChainNetwork

    async def example():
        manager = await get_chain_manager()

        # Get client for specific chain
        base_client = manager.get_client(ChainNetwork.BASE)

        # Check VIRTUAL balance
        balance = await base_client.get_virtual_balance("0x...")

        # Or use the primary chain client
        primary = manager.primary_client

Note: Blockchain dependencies (web3, solders, solana) are optional.
      Chain clients will only be available if their dependencies are installed.
"""

from .base_client import (
    BaseChainClient,
    ChainClientError,
    ContractNotFoundError,
    InsufficientFundsError,
    MultiChainManager,
    TransactionFailedError,
    get_chain_manager,
)

# Lazy imports for optional blockchain dependencies
EVMChainClient = None
SolanaChainClient = None

try:
    from .evm_client import EVMChainClient
except ImportError:
    pass  # web3 not installed

try:
    from .solana_client import SolanaChainClient
except ImportError:
    pass  # solders/solana not installed

__all__ = [
    # Base classes and exceptions
    "BaseChainClient",
    "ChainClientError",
    "InsufficientFundsError",
    "TransactionFailedError",
    "ContractNotFoundError",
    # Chain implementations (may be None if dependencies not installed)
    "EVMChainClient",
    "SolanaChainClient",
    # Manager
    "MultiChainManager",
    "get_chain_manager",
]
