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
"""

from .base_client import (
    BaseChainClient,
    ChainClientError,
    InsufficientFundsError,
    TransactionFailedError,
    ContractNotFoundError,
    MultiChainManager,
    get_chain_manager,
)

from .evm_client import EVMChainClient
from .solana_client import SolanaChainClient

__all__ = [
    # Base classes and exceptions
    "BaseChainClient",
    "ChainClientError",
    "InsufficientFundsError",
    "TransactionFailedError",
    "ContractNotFoundError",
    # Chain implementations
    "EVMChainClient",
    "SolanaChainClient",
    # Manager
    "MultiChainManager",
    "get_chain_manager",
]
