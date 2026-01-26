"""
Multi-Chain Client Base

This module provides the abstract base class for blockchain interactions
across different chains (Base, Ethereum, Solana). Each chain implementation
inherits from this base and provides chain-specific logic.

The multi-chain architecture enables Forge to:
- Deploy agents on the most suitable chain
- Bridge tokens between chains
- Execute transactions on multiple networks
- Query state across the entire multi-chain ecosystem
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from ..config import ChainNetwork, get_virtuals_config
from ..models import TokenInfo, TransactionRecord, WalletInfo

logger = logging.getLogger(__name__)


class ChainClientError(Exception):
    """Base exception for chain client errors."""
    pass


class InsufficientFundsError(ChainClientError):
    """Raised when wallet has insufficient funds for operation."""
    pass


class TransactionFailedError(ChainClientError):
    """Raised when a transaction fails to execute."""
    pass


class ContractNotFoundError(ChainClientError):
    """Raised when a contract address is not found or invalid."""
    pass


class BaseChainClient(ABC):
    """
    Abstract base class for blockchain client implementations.

    This class defines the interface that all chain-specific clients
    must implement, ensuring consistent behavior across different
    blockchain networks.

    The client handles:
    - Wallet management and balance queries
    - Transaction submission and monitoring
    - Contract interactions
    - Token operations (transfer, approve, etc.)
    """

    def __init__(self, chain: ChainNetwork):
        """
        Initialize the chain client.

        Args:
            chain: The blockchain network this client connects to
        """
        self.chain = chain
        self.config = get_virtuals_config()
        self._rpc_endpoint = self.config.get_rpc_endpoint(chain)
        self._initialized = False

    @abstractmethod
    async def initialize(self) -> None:
        """
        Initialize the chain connection and verify connectivity.

        This method should establish connection to the RPC endpoint
        and verify that the chain is accessible.
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close the chain connection and cleanup resources."""
        pass

    # ==================== Wallet Operations ====================

    @abstractmethod
    async def get_wallet_balance(
        self,
        address: str,
        token_address: str | None = None
    ) -> float:
        """
        Get the balance of a wallet.

        Args:
            address: The wallet address to query
            token_address: Optional token contract address. If None, returns
                          native currency balance (ETH, SOL, etc.)

        Returns:
            Balance as a float (human-readable units, not wei/lamports)
        """
        pass

    @abstractmethod
    async def get_virtual_balance(self, address: str) -> float:
        """
        Get the VIRTUAL token balance for a wallet.

        This is a convenience method that queries the VIRTUAL token
        balance specifically, since it's central to all operations.

        Args:
            address: The wallet address to query

        Returns:
            VIRTUAL token balance
        """
        pass

    @abstractmethod
    async def create_wallet(self) -> tuple[WalletInfo, str]:
        """
        Create a new wallet on this chain.

        Returns:
            Tuple of (WalletInfo, private_key_string)
            - WalletInfo: Wallet metadata
            - private_key_string: The private key as string (STORE SECURELY!)

        Security Warning:
            The private key is returned ONLY ONCE.
            NEVER log or store in plaintext. Use HSM or encrypted key storage.
        """
        pass

    # ==================== Transaction Operations ====================

    @abstractmethod
    async def send_transaction(
        self,
        to_address: str,
        value: float = 0,
        data: bytes | None = None,
        gas_limit: int | None = None,
    ) -> TransactionRecord:
        """
        Send a transaction on the chain.

        Args:
            to_address: Recipient address
            value: Amount of native currency to send
            data: Optional calldata for contract interactions
            gas_limit: Optional gas limit override

        Returns:
            TransactionRecord with the submitted transaction details
        """
        pass

    @abstractmethod
    async def wait_for_transaction(
        self,
        tx_hash: str,
        timeout_seconds: int = 120
    ) -> TransactionRecord:
        """
        Wait for a transaction to be confirmed.

        Args:
            tx_hash: The transaction hash to monitor
            timeout_seconds: Maximum time to wait for confirmation

        Returns:
            Updated TransactionRecord with confirmation details

        Raises:
            TimeoutError: If transaction not confirmed within timeout
            TransactionFailedError: If transaction reverts
        """
        pass

    @abstractmethod
    async def get_transaction(self, tx_hash: str) -> TransactionRecord | None:
        """
        Get details of a specific transaction.

        Args:
            tx_hash: The transaction hash to query

        Returns:
            TransactionRecord if found, None otherwise
        """
        pass

    @abstractmethod
    async def estimate_gas(
        self,
        to_address: str,
        value: float = 0,
        data: bytes | None = None,
    ) -> int:
        """
        Estimate gas required for a transaction.

        Args:
            to_address: Recipient address
            value: Amount to send
            data: Optional calldata

        Returns:
            Estimated gas units required
        """
        pass

    # ==================== Token Operations ====================

    @abstractmethod
    async def transfer_tokens(
        self,
        token_address: str,
        to_address: str,
        amount: float,
    ) -> TransactionRecord:
        """
        Transfer tokens to another address.

        Args:
            token_address: The token contract address
            to_address: Recipient address
            amount: Amount to transfer (human-readable units)

        Returns:
            TransactionRecord of the transfer
        """
        pass

    @abstractmethod
    async def approve_tokens(
        self,
        token_address: str,
        spender_address: str,
        amount: float,
    ) -> TransactionRecord:
        """
        Approve a spender to use tokens.

        Args:
            token_address: The token contract address
            spender_address: Address being approved to spend
            amount: Amount to approve (use float('inf') for unlimited)

        Returns:
            TransactionRecord of the approval
        """
        pass

    @abstractmethod
    async def get_token_info(self, token_address: str) -> TokenInfo:
        """
        Get information about a token.

        Args:
            token_address: The token contract address

        Returns:
            TokenInfo with token details
        """
        pass

    # ==================== Contract Operations ====================

    @abstractmethod
    async def call_contract(
        self,
        contract_address: str,
        function_name: str,
        args: list[Any],
        abi: list[dict[str, Any]] | None = None,
    ) -> Any:
        """
        Call a read-only contract function.

        Args:
            contract_address: The contract to call
            function_name: Name of the function to call
            args: Arguments to pass to the function
            abi: Optional ABI (uses cached ABI if not provided)

        Returns:
            The return value from the contract call
        """
        pass

    @abstractmethod
    async def execute_contract(
        self,
        contract_address: str,
        function_name: str,
        args: list[Any],
        value: float = 0,
        abi: list[dict[str, Any]] | None = None,
    ) -> TransactionRecord:
        """
        Execute a state-changing contract function.

        Args:
            contract_address: The contract to call
            function_name: Name of the function to execute
            args: Arguments to pass to the function
            value: Native currency to send with the call
            abi: Optional ABI (uses cached ABI if not provided)

        Returns:
            TransactionRecord of the execution
        """
        pass

    # ==================== Block Operations ====================

    @abstractmethod
    async def get_current_block(self) -> int:
        """Get the current block number."""
        pass

    @abstractmethod
    async def get_block_timestamp(self, block_number: int) -> datetime:
        """Get the timestamp of a specific block."""
        pass

    # ==================== Utility Methods ====================

    def get_contract_address(self, contract_name: str) -> str | None:
        """
        Get a known contract address for this chain.

        Args:
            contract_name: Name of the contract (e.g., 'virtual_token', 'agent_factory')

        Returns:
            Contract address if known, None otherwise
        """
        return self.config.get_contract_address(self.chain, contract_name)

    @property
    def virtual_token_address(self) -> str | None:
        """Get the VIRTUAL token address for this chain."""
        return self.get_contract_address("virtual_token")

    @property
    def is_initialized(self) -> bool:
        """Check if the client has been initialized."""
        return self._initialized

    def _ensure_initialized(self) -> None:
        """Raise error if client is not initialized."""
        if not self._initialized:
            raise ChainClientError(
                f"Chain client for {self.chain} not initialized. "
                "Call initialize() first."
            )


class MultiChainManager:
    """
    Manager for coordinating operations across multiple chains.

    This class provides a unified interface for multi-chain operations,
    routing requests to the appropriate chain client and handling
    cross-chain coordination.
    """

    def __init__(self) -> None:
        """Initialize the multi-chain manager."""
        self.config = get_virtuals_config()
        self._clients: dict[ChainNetwork, BaseChainClient] = {}
        self._initialized = False

    async def initialize(self) -> None:
        """
        Initialize all enabled chain clients.

        This method creates and initializes chain clients for each
        enabled chain in the configuration.
        """
        from .evm_client import EVMChainClient
        from .solana_client import SolanaChainClient

        for chain in self.config.enabled_chains:
            client: BaseChainClient
            if chain in [ChainNetwork.SOLANA, ChainNetwork.SOLANA_DEVNET]:
                client = SolanaChainClient(chain)
            else:
                client = EVMChainClient(chain)

            await client.initialize()
            self._clients[chain] = client
            logger.info(f"Initialized chain client for {chain}")

        self._initialized = True

    async def close(self) -> None:
        """Close all chain clients."""
        for client in self._clients.values():
            await client.close()
        self._clients.clear()
        self._initialized = False

    def get_client(self, chain: ChainNetwork) -> BaseChainClient:
        """
        Get the client for a specific chain.

        Args:
            chain: The chain to get the client for

        Returns:
            The chain client

        Raises:
            ChainClientError: If chain is not enabled or initialized
        """
        if chain not in self._clients:
            raise ChainClientError(
                f"Chain {chain} is not enabled or initialized"
            )
        return self._clients[chain]

    @property
    def primary_client(self) -> BaseChainClient:
        """Get the client for the primary chain."""
        return self.get_client(self.config.primary_chain)

    async def get_total_virtual_balance(self, addresses: dict[str, str]) -> float:
        """
        Get total VIRTUAL balance across all chains.

        Args:
            addresses: Dict mapping chain names to wallet addresses

        Returns:
            Total VIRTUAL balance across all chains
        """
        total = 0.0
        for chain_name, address in addresses.items():
            try:
                chain = ChainNetwork(chain_name)
                if chain in self._clients:
                    balance = await self._clients[chain].get_virtual_balance(address)
                    total += balance
            except Exception as e:
                logger.warning(f"Failed to get balance on {chain_name}: {e}")
        return total


# Global manager instance
_chain_manager: MultiChainManager | None = None


async def get_chain_manager() -> MultiChainManager:
    """
    Get the global multi-chain manager instance.

    Initializes the manager if not already done.
    """
    global _chain_manager
    if _chain_manager is None:
        _chain_manager = MultiChainManager()
        await _chain_manager.initialize()
    return _chain_manager
