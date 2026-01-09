"""
EVM Chain Client Implementation

This module provides the concrete implementation of the chain client
for EVM-compatible chains (Base, Ethereum). It uses web3.py for all
blockchain interactions.

The EVM client supports:
- Base (primary chain for Virtuals Protocol)
- Ethereum mainnet (for bridging and cross-chain operations)
- Testnets (Base Sepolia, Ethereum Sepolia) for development
"""

import asyncio
from datetime import datetime
from typing import Any, Optional
import logging

from web3 import AsyncWeb3, AsyncHTTPProvider
from web3.exceptions import ContractLogicError, TransactionNotFound
from eth_account import Account
from eth_account.signers.local import LocalAccount

from .base_client import (
    BaseChainClient,
    ChainClientError,
    InsufficientFundsError,
    TransactionFailedError,
    ContractNotFoundError,
)
from ..config import ChainNetwork, get_virtuals_config
from ..models import WalletInfo, TransactionRecord, TokenInfo


logger = logging.getLogger(__name__)


# Standard ERC-20 ABI for token operations
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "symbol",
        "outputs": [{"name": "", "type": "string"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "name",
        "outputs": [{"name": "", "type": "string"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "totalSupply",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_to", "type": "address"},
            {"name": "_value", "type": "uint256"},
        ],
        "name": "transfer",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_spender", "type": "address"},
            {"name": "_value", "type": "uint256"},
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [
            {"name": "_owner", "type": "address"},
            {"name": "_spender", "type": "address"},
        ],
        "name": "allowance",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
    },
]


class EVMChainClient(BaseChainClient):
    """
    Chain client implementation for EVM-compatible blockchains.
    
    This client handles all interactions with Base and Ethereum networks,
    providing a consistent interface for wallet operations, transactions,
    and smart contract interactions.
    """
    
    def __init__(self, chain: ChainNetwork):
        """
        Initialize the EVM chain client.
        
        The client is not connected until initialize() is called. This allows
        for lazy initialization and proper async setup. The constructor sets
        up the configuration and prepares the client state, while initialize()
        establishes the actual network connection.
        
        Args:
            chain: The EVM chain to connect to (BASE, ETHEREUM, or their testnets)
        """
        super().__init__(chain)
        self._w3: Optional[AsyncWeb3] = None
        self._operator_account: Optional[LocalAccount] = None
        self._contract_cache: dict[str, Any] = {}
        self._token_decimals_cache: dict[str, int] = {}
    
    async def initialize(self) -> None:
        """
        Initialize the chain connection and operator wallet.
        
        This method establishes the Web3 connection to the RPC endpoint and
        loads the operator account from the private key if configured. The
        operator account is used for signing transactions on behalf of Forge.
        """
        # Create async Web3 instance with the configured RPC endpoint
        self._w3 = AsyncWeb3(AsyncHTTPProvider(self._rpc_endpoint))
        
        # Verify connection by checking if we can reach the network
        try:
            chain_id = await self._w3.eth.chain_id
            logger.info(f"Connected to {self.chain} (chain_id: {chain_id})")
        except Exception as e:
            raise ChainClientError(f"Failed to connect to {self.chain}: {e}")
        
        # Load operator account if private key is configured. The operator
        # account is the wallet that signs transactions for Forge operations.
        if self.config.operator_private_key:
            try:
                self._operator_account = Account.from_key(
                    self.config.operator_private_key
                )
                logger.info(
                    f"Operator account loaded: {self._operator_account.address}"
                )
            except Exception as e:
                logger.warning(f"Failed to load operator account: {e}")
        
        self._initialized = True
    
    async def close(self) -> None:
        """
        Close the chain connection and cleanup resources.
        
        This properly disposes of the Web3 provider and clears cached data
        to prevent memory leaks during shutdown.
        """
        if self._w3 and hasattr(self._w3.provider, 'disconnect'):
            await self._w3.provider.disconnect()
        self._w3 = None
        self._operator_account = None
        self._contract_cache.clear()
        self._token_decimals_cache.clear()
        self._initialized = False
    
    # ==================== Wallet Operations ====================
    
    async def get_wallet_balance(
        self, 
        address: str, 
        token_address: Optional[str] = None
    ) -> float:
        """
        Get the balance of a wallet.
        
        This method queries either the native currency balance (ETH on Ethereum,
        ETH on Base) or an ERC-20 token balance. All balances are returned in
        human-readable units (e.g., 1.5 ETH, not 1500000000000000000 wei).
        
        Args:
            address: The wallet address to query
            token_address: Optional ERC-20 token address. If None, returns
                          the native currency balance.
        
        Returns:
            Balance in human-readable units
        """
        self._ensure_initialized()
        
        # Validate and checksum the address to prevent errors
        address = self._w3.to_checksum_address(address)
        
        if token_address is None:
            # Query native currency balance (wei) and convert to ETH
            balance_wei = await self._w3.eth.get_balance(address)
            return float(self._w3.from_wei(balance_wei, 'ether'))
        else:
            # Query ERC-20 token balance using the standard balanceOf function
            token_address = self._w3.to_checksum_address(token_address)
            contract = self._get_token_contract(token_address)
            
            # Get raw balance and decimals for conversion
            balance_raw = await contract.functions.balanceOf(address).call()
            decimals = await self._get_token_decimals(token_address)
            
            # Convert from smallest unit to human-readable
            return balance_raw / (10 ** decimals)
    
    async def get_virtual_balance(self, address: str) -> float:
        """
        Get the VIRTUAL token balance for a wallet.
        
        This is a convenience method since VIRTUAL is the primary token
        used throughout the Virtuals Protocol ecosystem.
        
        Args:
            address: The wallet address to query
            
        Returns:
            VIRTUAL token balance
        """
        virtual_address = self.virtual_token_address
        if not virtual_address:
            raise ChainClientError(
                f"VIRTUAL token address not configured for {self.chain}"
            )
        return await self.get_wallet_balance(address, virtual_address)
    
    async def create_wallet(self) -> tuple[WalletInfo, str]:
        """
        SECURITY FIX (Audit 4): Create a new wallet and return private key.

        Generates a new random Ethereum account. The private key is returned
        and MUST be stored securely using a key management system or HSM.

        CRITICAL: The private key is returned ONLY ONCE. If not stored,
        funds sent to this wallet will be PERMANENTLY LOST.

        Returns:
            Tuple of (WalletInfo, private_key_hex)
            - WalletInfo: Wallet metadata
            - private_key_hex: The private key as hex string (STORE SECURELY!)

        Note:
            This creates an externally owned account (EOA). Token-bound
            accounts (TBAs) are created differently through the ERC-6551
            factory contract.

        Security Warning:
            - NEVER log the private key
            - NEVER store in plaintext
            - Use HSM or encrypted key storage
            - Consider using a key derivation path instead for HD wallets
        """
        self._ensure_initialized()

        # Generate a new random account
        account = Account.create()

        # SECURITY FIX (Audit 4): Return private key so it can be stored
        private_key_hex = account.key.hex()

        import structlog
        structlog.get_logger().info(
            "wallet_created",
            address=account.address,
            chain=self.chain.value,
            warning="Private key returned - MUST be stored securely by caller!",
        )

        wallet_info = WalletInfo(
            address=account.address,
            chain=self.chain.value,
            wallet_type="eoa",
            is_token_bound=False,
            balance_virtual=0.0,
        )

        return wallet_info, private_key_hex
    
    # ==================== Transaction Operations ====================
    
    async def send_transaction(
        self,
        to_address: str,
        value: float = 0,
        data: Optional[bytes] = None,
        gas_limit: Optional[int] = None,
    ) -> TransactionRecord:
        """
        Send a transaction on the chain.
        
        This method builds, signs, and broadcasts a transaction using the
        operator account. It handles gas estimation, nonce management, and
        EIP-1559 fee calculation automatically.
        
        Args:
            to_address: Recipient address
            value: Amount of native currency to send (in ETH units)
            data: Optional calldata for contract interactions
            gas_limit: Optional gas limit override
            
        Returns:
            TransactionRecord with submitted transaction details
        """
        self._ensure_initialized()
        
        if not self._operator_account:
            raise ChainClientError("No operator account configured")
        
        to_address = self._w3.to_checksum_address(to_address)
        value_wei = self._w3.to_wei(value, 'ether')
        
        # Build the transaction with EIP-1559 fee parameters
        tx = {
            'from': self._operator_account.address,
            'to': to_address,
            'value': value_wei,
            'nonce': await self._w3.eth.get_transaction_count(
                self._operator_account.address
            ),
            'chainId': await self._w3.eth.chain_id,
        }
        
        # Add calldata if provided
        if data:
            tx['data'] = data
        
        # Estimate gas if not provided
        if gas_limit:
            tx['gas'] = gas_limit
        else:
            tx['gas'] = await self._w3.eth.estimate_gas(tx)
        
        # Get EIP-1559 fee parameters
        base_fee = (await self._w3.eth.get_block('latest'))['baseFeePerGas']
        max_priority_fee = await self._w3.eth.max_priority_fee
        tx['maxFeePerGas'] = base_fee * 2 + max_priority_fee
        tx['maxPriorityFeePerGas'] = max_priority_fee
        
        # Sign and send the transaction
        signed_tx = self._operator_account.sign_transaction(tx)
        tx_hash = await self._w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        
        return TransactionRecord(
            tx_hash=tx_hash.hex(),
            chain=self.chain.value,
            block_number=0,  # Will be filled when confirmed
            timestamp=datetime.utcnow(),
            from_address=self._operator_account.address,
            to_address=to_address,
            value=value,
            gas_used=0,  # Will be filled when confirmed
            status="pending",
            transaction_type="transfer" if not data else "contract_call",
        )
    
    async def wait_for_transaction(
        self, 
        tx_hash: str, 
        timeout_seconds: int = 120
    ) -> TransactionRecord:
        """
        Wait for a transaction to be confirmed.
        
        This method polls the chain for the transaction receipt until it's
        confirmed or the timeout is reached. It uses exponential backoff
        to avoid overwhelming the RPC endpoint.
        
        Args:
            tx_hash: The transaction hash to monitor
            timeout_seconds: Maximum time to wait
            
        Returns:
            Updated TransactionRecord with confirmation details
        """
        self._ensure_initialized()
        
        # Poll for receipt with exponential backoff
        start_time = asyncio.get_event_loop().time()
        poll_interval = 1.0
        
        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > timeout_seconds:
                raise TimeoutError(
                    f"Transaction {tx_hash} not confirmed within {timeout_seconds}s"
                )
            
            try:
                receipt = await self._w3.eth.get_transaction_receipt(tx_hash)
                if receipt:
                    # Transaction confirmed
                    tx = await self._w3.eth.get_transaction(tx_hash)
                    block = await self._w3.eth.get_block(receipt['blockNumber'])
                    
                    status = "success" if receipt['status'] == 1 else "failed"
                    if status == "failed":
                        raise TransactionFailedError(
                            f"Transaction {tx_hash} reverted"
                        )
                    
                    return TransactionRecord(
                        tx_hash=tx_hash,
                        chain=self.chain.value,
                        block_number=receipt['blockNumber'],
                        timestamp=datetime.fromtimestamp(block['timestamp']),
                        from_address=tx['from'],
                        to_address=tx['to'] or "",
                        value=float(self._w3.from_wei(tx['value'], 'ether')),
                        gas_used=receipt['gasUsed'],
                        status=status,
                        transaction_type="transfer",
                    )
            except TransactionNotFound:
                pass  # Transaction not yet confirmed
            
            await asyncio.sleep(poll_interval)
            poll_interval = min(poll_interval * 1.5, 10.0)  # Cap at 10 seconds
    
    async def get_transaction(self, tx_hash: str) -> Optional[TransactionRecord]:
        """Get details of a specific transaction."""
        self._ensure_initialized()
        
        try:
            tx = await self._w3.eth.get_transaction(tx_hash)
            if not tx:
                return None
            
            receipt = await self._w3.eth.get_transaction_receipt(tx_hash)
            
            if receipt:
                block = await self._w3.eth.get_block(receipt['blockNumber'])
                status = "success" if receipt['status'] == 1 else "failed"
                timestamp = datetime.fromtimestamp(block['timestamp'])
            else:
                status = "pending"
                timestamp = datetime.utcnow()
            
            return TransactionRecord(
                tx_hash=tx_hash,
                chain=self.chain.value,
                block_number=receipt['blockNumber'] if receipt else 0,
                timestamp=timestamp,
                from_address=tx['from'],
                to_address=tx['to'] or "",
                value=float(self._w3.from_wei(tx['value'], 'ether')),
                gas_used=receipt['gasUsed'] if receipt else 0,
                status=status,
                transaction_type="transfer",
            )
        except TransactionNotFound:
            return None
    
    async def estimate_gas(
        self,
        to_address: str,
        value: float = 0,
        data: Optional[bytes] = None,
    ) -> int:
        """Estimate gas required for a transaction."""
        self._ensure_initialized()
        
        tx = {
            'to': self._w3.to_checksum_address(to_address),
            'value': self._w3.to_wei(value, 'ether'),
        }
        if data:
            tx['data'] = data
        if self._operator_account:
            tx['from'] = self._operator_account.address
        
        return await self._w3.eth.estimate_gas(tx)
    
    # ==================== Token Operations ====================
    
    async def transfer_tokens(
        self,
        token_address: str,
        to_address: str,
        amount: float,
    ) -> TransactionRecord:
        """
        Transfer ERC-20 tokens to another address.
        
        This encodes the transfer function call and sends it as a transaction.
        The amount is automatically converted from human-readable units to
        the token's smallest unit based on its decimals.
        """
        self._ensure_initialized()
        
        token_address = self._w3.to_checksum_address(token_address)
        to_address = self._w3.to_checksum_address(to_address)
        
        # Get decimals and convert amount
        decimals = await self._get_token_decimals(token_address)
        amount_raw = int(amount * (10 ** decimals))
        
        # Encode the transfer function call
        contract = self._get_token_contract(token_address)
        data = contract.encodeABI(
            fn_name='transfer',
            args=[to_address, amount_raw]
        )
        
        # Send the transaction
        tx_record = await self.send_transaction(
            to_address=token_address,
            value=0,
            data=bytes.fromhex(data[2:]),  # Remove '0x' prefix
        )
        tx_record.transaction_type = "token_transfer"
        return tx_record
    
    async def approve_tokens(
        self,
        token_address: str,
        spender_address: str,
        amount: float,
    ) -> TransactionRecord:
        """
        Approve a spender to use tokens.
        
        This is required before other contracts can transfer tokens on behalf
        of the wallet. Many DeFi operations require an approval step first.
        """
        self._ensure_initialized()
        
        token_address = self._w3.to_checksum_address(token_address)
        spender_address = self._w3.to_checksum_address(spender_address)
        
        # Handle unlimited approval
        if amount == float('inf'):
            amount_raw = 2**256 - 1  # Max uint256
        else:
            decimals = await self._get_token_decimals(token_address)
            amount_raw = int(amount * (10 ** decimals))
        
        # Encode the approve function call
        contract = self._get_token_contract(token_address)
        data = contract.encodeABI(
            fn_name='approve',
            args=[spender_address, amount_raw]
        )
        
        tx_record = await self.send_transaction(
            to_address=token_address,
            value=0,
            data=bytes.fromhex(data[2:]),
        )
        tx_record.transaction_type = "token_approval"
        return tx_record
    
    async def get_token_info(self, token_address: str) -> TokenInfo:
        """Get comprehensive information about an ERC-20 token."""
        self._ensure_initialized()
        
        token_address = self._w3.to_checksum_address(token_address)
        contract = self._get_token_contract(token_address)
        
        # Fetch all token metadata in parallel for efficiency
        name, symbol, decimals, total_supply = await asyncio.gather(
            contract.functions.name().call(),
            contract.functions.symbol().call(),
            contract.functions.decimals().call(),
            contract.functions.totalSupply().call(),
        )
        
        return TokenInfo(
            token_address=token_address,
            chain=self.chain.value,
            symbol=symbol,
            name=name,
            total_supply=total_supply // (10 ** decimals),
            circulating_supply=total_supply // (10 ** decimals),
        )
    
    # ==================== Contract Operations ====================
    
    async def call_contract(
        self,
        contract_address: str,
        function_name: str,
        args: list[Any],
        abi: Optional[list[dict]] = None,
    ) -> Any:
        """
        Call a read-only contract function.
        
        This executes a view/pure function on a contract without sending
        a transaction. No gas is consumed for read operations.
        """
        self._ensure_initialized()
        
        contract_address = self._w3.to_checksum_address(contract_address)
        
        if abi is None:
            raise ChainClientError("ABI required for contract calls")
        
        contract = self._w3.eth.contract(address=contract_address, abi=abi)
        func = getattr(contract.functions, function_name)
        return await func(*args).call()
    
    async def execute_contract(
        self,
        contract_address: str,
        function_name: str,
        args: list[Any],
        value: float = 0,
        abi: Optional[list[dict]] = None,
    ) -> TransactionRecord:
        """
        Execute a state-changing contract function.
        
        This sends a transaction that modifies contract state. The function
        must be non-view/non-pure and may require gas payment.
        """
        self._ensure_initialized()
        
        if abi is None:
            raise ChainClientError("ABI required for contract execution")
        
        contract_address = self._w3.to_checksum_address(contract_address)
        contract = self._w3.eth.contract(address=contract_address, abi=abi)
        
        func = getattr(contract.functions, function_name)
        data = func(*args).build_transaction({'from': self._operator_account.address})['data']
        
        tx_record = await self.send_transaction(
            to_address=contract_address,
            value=value,
            data=bytes.fromhex(data[2:]),
        )
        tx_record.transaction_type = f"contract_{function_name}"
        return tx_record
    
    # ==================== Block Operations ====================
    
    async def get_current_block(self) -> int:
        """Get the current block number."""
        self._ensure_initialized()
        return await self._w3.eth.block_number
    
    async def get_block_timestamp(self, block_number: int) -> datetime:
        """Get the timestamp of a specific block."""
        self._ensure_initialized()
        block = await self._w3.eth.get_block(block_number)
        return datetime.fromtimestamp(block['timestamp'])
    
    # ==================== Helper Methods ====================
    
    def _get_token_contract(self, token_address: str):
        """Get or create a contract instance for a token."""
        if token_address not in self._contract_cache:
            self._contract_cache[token_address] = self._w3.eth.contract(
                address=self._w3.to_checksum_address(token_address),
                abi=ERC20_ABI,
            )
        return self._contract_cache[token_address]
    
    async def _get_token_decimals(self, token_address: str) -> int:
        """Get and cache the decimals for a token."""
        if token_address not in self._token_decimals_cache:
            contract = self._get_token_contract(token_address)
            self._token_decimals_cache[token_address] = await contract.functions.decimals().call()
        return self._token_decimals_cache[token_address]
