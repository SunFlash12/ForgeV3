"""
Solana Chain Client Implementation

This module provides the concrete implementation of the chain client
for Solana. It uses the solana-py library for all blockchain interactions.

Solana support enables:
- Cross-chain agent deployment
- Token bridging via Wormhole
- Access to Solana-native DeFi and NFT ecosystems
- Lower transaction costs for high-frequency operations
"""

import asyncio
from datetime import datetime
from typing import Any, Optional
import logging
import base58

from .base_client import (
    BaseChainClient,
    ChainClientError,
    InsufficientFundsError,
    TransactionFailedError,
)
from ..config import ChainNetwork, get_virtuals_config
from ..models import WalletInfo, TransactionRecord, TokenInfo


logger = logging.getLogger(__name__)


class SolanaChainClient(BaseChainClient):
    """
    Chain client implementation for Solana.
    
    This client handles all interactions with Solana mainnet and devnet,
    providing a consistent interface for wallet operations, transactions,
    and program interactions.
    
    Note: Solana uses different terminology and paradigms than EVM chains:
    - Programs instead of smart contracts
    - Accounts instead of addresses (more complex state model)
    - Lamports instead of wei (1 SOL = 1 billion lamports)
    - SPL tokens instead of ERC-20
    """
    
    def __init__(self, chain: ChainNetwork):
        """
        Initialize the Solana chain client.
        
        Args:
            chain: SOLANA or SOLANA_DEVNET
        """
        super().__init__(chain)
        self._client = None  # AsyncClient from solana-py
        self._keypair = None  # Operator keypair
        self._token_program_id = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
    
    async def initialize(self) -> None:
        """
        Initialize the Solana connection and operator keypair.
        
        This method establishes the connection to the Solana RPC endpoint
        and loads the operator keypair from the private key if configured.
        """
        try:
            # Import Solana libraries (lazy import to handle optional dependency)
            from solana.rpc.async_api import AsyncClient
            from solders.keypair import Keypair
            
            # Create async client with the configured RPC endpoint
            self._client = AsyncClient(self._rpc_endpoint)
            
            # Verify connection by getting the latest blockhash
            response = await self._client.get_latest_blockhash()
            if response.value is None:
                raise ChainClientError("Failed to connect to Solana RPC")
            
            logger.info(f"Connected to Solana ({self.chain})")
            
            # Load operator keypair if private key is configured
            if self.config.solana_private_key:
                try:
                    # Solana private keys are typically base58 encoded
                    secret_key = base58.b58decode(self.config.solana_private_key)
                    self._keypair = Keypair.from_bytes(secret_key)
                    logger.info(f"Operator keypair loaded: {self._keypair.pubkey()}")
                except Exception as e:
                    logger.warning(f"Failed to load Solana operator keypair: {e}")
            
            self._initialized = True
            
        except ImportError:
            raise ChainClientError(
                "Solana dependencies not installed. "
                "Install with: pip install solana solders"
            )
    
    async def close(self) -> None:
        """Close the Solana connection and cleanup resources."""
        if self._client:
            await self._client.close()
        self._client = None
        self._keypair = None
        self._initialized = False
    
    # ==================== Wallet Operations ====================
    
    async def get_wallet_balance(
        self, 
        address: str, 
        token_address: Optional[str] = None
    ) -> float:
        """
        Get the balance of a Solana wallet.
        
        Args:
            address: The wallet public key (base58 encoded)
            token_address: Optional SPL token mint address. If None, returns
                          SOL balance.
        
        Returns:
            Balance in human-readable units (SOL or token amount)
        """
        self._ensure_initialized()
        from solders.pubkey import Pubkey
        
        pubkey = Pubkey.from_string(address)
        
        if token_address is None:
            # Query SOL balance (in lamports) and convert to SOL
            response = await self._client.get_balance(pubkey)
            if response.value is None:
                return 0.0
            return response.value / 1_000_000_000  # Lamports to SOL
        else:
            # Query SPL token balance. This requires finding the associated
            # token account (ATA) for the wallet and token mint.
            token_mint = Pubkey.from_string(token_address)
            
            # Get all token accounts for this wallet with the specified mint
            response = await self._client.get_token_accounts_by_owner(
                pubkey,
                opts={"mint": token_mint},
            )
            
            if not response.value:
                return 0.0
            
            # Sum up balances from all matching token accounts
            total_balance = 0
            for account in response.value:
                # Parse the account data to get the token balance
                account_data = account.account.data
                # Token account data structure: amount is at bytes 64-72
                if len(account_data) >= 72:
                    amount = int.from_bytes(account_data[64:72], 'little')
                    total_balance += amount
            
            # Get decimals for proper conversion
            decimals = await self._get_token_decimals(token_address)
            return total_balance / (10 ** decimals)
    
    async def get_virtual_balance(self, address: str) -> float:
        """
        Get the VIRTUAL token balance for a Solana wallet.
        
        VIRTUAL on Solana is an SPL token with a specific mint address.
        """
        virtual_address = self.virtual_token_address
        if not virtual_address:
            raise ChainClientError(
                f"VIRTUAL token address not configured for {self.chain}"
            )
        return await self.get_wallet_balance(address, virtual_address)
    
    async def create_wallet(self) -> WalletInfo:
        """
        Create a new Solana wallet.
        
        Generates a new Ed25519 keypair. The secret key should be stored
        securely using the application's key management system.
        """
        self._ensure_initialized()
        from solders.keypair import Keypair
        
        # Generate a new random keypair
        keypair = Keypair()
        
        return WalletInfo(
            address=str(keypair.pubkey()),
            chain=self.chain.value,
            wallet_type="eoa",
            is_token_bound=False,
            balance_virtual=0.0,
        )
    
    # ==================== Transaction Operations ====================
    
    async def send_transaction(
        self,
        to_address: str,
        value: float = 0,
        data: Optional[bytes] = None,
        gas_limit: Optional[int] = None,
    ) -> TransactionRecord:
        """
        Send a SOL transfer transaction.
        
        Note: Unlike EVM chains, Solana transactions for program interactions
        require different construction. This method handles simple SOL transfers.
        For program interactions, use execute_contract instead.
        """
        self._ensure_initialized()
        
        if not self._keypair:
            raise ChainClientError("No operator keypair configured")
        
        from solders.pubkey import Pubkey
        from solders.system_program import transfer, TransferParams
        from solana.transaction import Transaction
        
        to_pubkey = Pubkey.from_string(to_address)
        lamports = int(value * 1_000_000_000)  # SOL to lamports
        
        # Build the transfer instruction
        transfer_ix = transfer(
            TransferParams(
                from_pubkey=self._keypair.pubkey(),
                to_pubkey=to_pubkey,
                lamports=lamports,
            )
        )
        
        # Create and sign the transaction
        recent_blockhash = (await self._client.get_latest_blockhash()).value.blockhash
        tx = Transaction(
            recent_blockhash=recent_blockhash,
            fee_payer=self._keypair.pubkey(),
        )
        tx.add(transfer_ix)
        tx.sign(self._keypair)
        
        # Send the transaction
        response = await self._client.send_transaction(tx)
        
        if response.value is None:
            raise TransactionFailedError("Failed to send Solana transaction")
        
        tx_sig = str(response.value)
        
        return TransactionRecord(
            tx_hash=tx_sig,
            chain=self.chain.value,
            block_number=0,
            timestamp=datetime.utcnow(),
            from_address=str(self._keypair.pubkey()),
            to_address=to_address,
            value=value,
            gas_used=0,  # Solana uses compute units, not gas
            status="pending",
            transaction_type="transfer",
        )
    
    async def wait_for_transaction(
        self, 
        tx_hash: str, 
        timeout_seconds: int = 120
    ) -> TransactionRecord:
        """
        Wait for a Solana transaction to be confirmed.
        
        Solana has faster block times (~400ms) but requires waiting for
        sufficient confirmations for finality.
        """
        self._ensure_initialized()
        from solders.signature import Signature
        
        signature = Signature.from_string(tx_hash)
        
        # Wait for confirmation with timeout
        start_time = asyncio.get_event_loop().time()
        
        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > timeout_seconds:
                raise TimeoutError(
                    f"Transaction {tx_hash} not confirmed within {timeout_seconds}s"
                )
            
            response = await self._client.get_signature_statuses([signature])
            
            if response.value and response.value[0]:
                status = response.value[0]
                
                if status.err:
                    raise TransactionFailedError(
                        f"Transaction {tx_hash} failed: {status.err}"
                    )
                
                if status.confirmation_status in ["confirmed", "finalized"]:
                    # Get transaction details for complete record
                    tx_response = await self._client.get_transaction(signature)
                    
                    return TransactionRecord(
                        tx_hash=tx_hash,
                        chain=self.chain.value,
                        block_number=status.slot,
                        timestamp=datetime.utcnow(),
                        from_address="",  # Would need to parse from tx
                        to_address="",
                        value=0,
                        gas_used=tx_response.value.meta.compute_units_consumed if tx_response.value else 0,
                        status="success",
                        transaction_type="transfer",
                    )
            
            await asyncio.sleep(0.5)  # Solana has fast blocks
    
    async def get_transaction(self, tx_hash: str) -> Optional[TransactionRecord]:
        """Get details of a specific Solana transaction."""
        self._ensure_initialized()
        from solders.signature import Signature
        
        try:
            signature = Signature.from_string(tx_hash)
            response = await self._client.get_transaction(signature)
            
            if response.value is None:
                return None
            
            tx = response.value
            
            return TransactionRecord(
                tx_hash=tx_hash,
                chain=self.chain.value,
                block_number=tx.slot,
                timestamp=datetime.fromtimestamp(tx.block_time) if tx.block_time else datetime.utcnow(),
                from_address="",
                to_address="",
                value=0,
                gas_used=tx.meta.compute_units_consumed if tx.meta else 0,
                status="success" if tx.meta and not tx.meta.err else "failed",
                transaction_type="unknown",
            )
        except Exception as e:
            logger.error(f"Failed to get Solana transaction {tx_hash}: {e}")
            return None
    
    async def estimate_gas(
        self,
        to_address: str,
        value: float = 0,
        data: Optional[bytes] = None,
    ) -> int:
        """
        Estimate compute units for a Solana transaction.
        
        Note: Solana uses "compute units" instead of gas. The default
        compute unit limit is 200,000 per instruction.
        """
        # Solana compute units are more predictable than EVM gas
        # A simple SOL transfer uses ~450 compute units
        # Complex program interactions use more
        return 200_000  # Default safe estimate
    
    # ==================== Token Operations ====================
    
    async def transfer_tokens(
        self,
        token_address: str,
        to_address: str,
        amount: float,
    ) -> TransactionRecord:
        """
        Transfer SPL tokens to another address.
        
        This creates or uses the recipient's associated token account (ATA)
        and performs the SPL token transfer.
        """
        self._ensure_initialized()
        
        if not self._keypair:
            raise ChainClientError("No operator keypair configured")
        
        from solders.pubkey import Pubkey
        from spl.token.instructions import transfer_checked, TransferCheckedParams
        from spl.token.constants import TOKEN_PROGRAM_ID
        from solana.transaction import Transaction
        
        token_mint = Pubkey.from_string(token_address)
        to_pubkey = Pubkey.from_string(to_address)
        
        # Get decimals for the token
        decimals = await self._get_token_decimals(token_address)
        amount_raw = int(amount * (10 ** decimals))
        
        # Find associated token accounts
        source_ata = self._get_associated_token_address(
            self._keypair.pubkey(), token_mint
        )
        dest_ata = self._get_associated_token_address(to_pubkey, token_mint)
        
        # Build transfer instruction
        transfer_ix = transfer_checked(
            TransferCheckedParams(
                program_id=TOKEN_PROGRAM_ID,
                source=source_ata,
                mint=token_mint,
                dest=dest_ata,
                owner=self._keypair.pubkey(),
                amount=amount_raw,
                decimals=decimals,
            )
        )
        
        # Create and sign transaction
        recent_blockhash = (await self._client.get_latest_blockhash()).value.blockhash
        tx = Transaction(
            recent_blockhash=recent_blockhash,
            fee_payer=self._keypair.pubkey(),
        )
        tx.add(transfer_ix)
        tx.sign(self._keypair)
        
        response = await self._client.send_transaction(tx)
        
        if response.value is None:
            raise TransactionFailedError("Failed to send SPL token transfer")
        
        tx_record = TransactionRecord(
            tx_hash=str(response.value),
            chain=self.chain.value,
            block_number=0,
            timestamp=datetime.utcnow(),
            from_address=str(self._keypair.pubkey()),
            to_address=to_address,
            value=amount,
            gas_used=0,
            status="pending",
            transaction_type="token_transfer",
        )
        
        return tx_record
    
    async def approve_tokens(
        self,
        token_address: str,
        spender_address: str,
        amount: float,
    ) -> TransactionRecord:
        """
        Approve a delegate to transfer SPL tokens.
        
        Note: SPL tokens use "delegate" terminology instead of "approve/spender".
        """
        self._ensure_initialized()
        
        if not self._keypair:
            raise ChainClientError("No operator keypair configured")
        
        from solders.pubkey import Pubkey
        from spl.token.instructions import approve, ApproveParams
        from spl.token.constants import TOKEN_PROGRAM_ID
        from solana.transaction import Transaction
        
        token_mint = Pubkey.from_string(token_address)
        delegate = Pubkey.from_string(spender_address)
        
        decimals = await self._get_token_decimals(token_address)
        
        if amount == float('inf'):
            amount_raw = 2**64 - 1  # Max u64 for SPL tokens
        else:
            amount_raw = int(amount * (10 ** decimals))
        
        source_ata = self._get_associated_token_address(
            self._keypair.pubkey(), token_mint
        )
        
        approve_ix = approve(
            ApproveParams(
                program_id=TOKEN_PROGRAM_ID,
                source=source_ata,
                delegate=delegate,
                owner=self._keypair.pubkey(),
                amount=amount_raw,
            )
        )
        
        recent_blockhash = (await self._client.get_latest_blockhash()).value.blockhash
        tx = Transaction(
            recent_blockhash=recent_blockhash,
            fee_payer=self._keypair.pubkey(),
        )
        tx.add(approve_ix)
        tx.sign(self._keypair)
        
        response = await self._client.send_transaction(tx)
        
        if response.value is None:
            raise TransactionFailedError("Failed to approve SPL tokens")
        
        return TransactionRecord(
            tx_hash=str(response.value),
            chain=self.chain.value,
            block_number=0,
            timestamp=datetime.utcnow(),
            from_address=str(self._keypair.pubkey()),
            to_address=spender_address,
            value=amount,
            gas_used=0,
            status="pending",
            transaction_type="token_approval",
        )
    
    async def get_token_info(self, token_address: str) -> TokenInfo:
        """Get information about an SPL token."""
        self._ensure_initialized()
        from solders.pubkey import Pubkey
        
        token_mint = Pubkey.from_string(token_address)
        
        # Get mint account data
        response = await self._client.get_account_info(token_mint)
        
        if response.value is None:
            raise ChainClientError(f"Token mint not found: {token_address}")
        
        # Parse mint data (Mint account structure)
        data = response.value.data
        decimals = data[44] if len(data) > 44 else 9
        supply = int.from_bytes(data[36:44], 'little') if len(data) >= 44 else 0
        
        return TokenInfo(
            token_address=token_address,
            chain=self.chain.value,
            symbol="UNKNOWN",  # Solana doesn't store symbol in mint
            name="Unknown Token",
            total_supply=supply // (10 ** decimals),
            circulating_supply=supply // (10 ** decimals),
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
        Read data from a Solana program.
        
        Note: Solana programs work differently than EVM contracts.
        This is a placeholder that would need program-specific implementation.
        """
        raise NotImplementedError(
            "Solana program calls require program-specific implementation"
        )
    
    async def execute_contract(
        self,
        contract_address: str,
        function_name: str,
        args: list[Any],
        value: float = 0,
        abi: Optional[list[dict]] = None,
    ) -> TransactionRecord:
        """
        Execute a Solana program instruction.
        
        Note: This requires program-specific instruction building.
        """
        raise NotImplementedError(
            "Solana program execution requires program-specific implementation"
        )
    
    # ==================== Block Operations ====================
    
    async def get_current_block(self) -> int:
        """Get the current slot (Solana's equivalent of block number)."""
        self._ensure_initialized()
        response = await self._client.get_slot()
        return response.value
    
    async def get_block_timestamp(self, block_number: int) -> datetime:
        """Get the timestamp of a specific slot."""
        self._ensure_initialized()
        response = await self._client.get_block_time(block_number)
        if response.value:
            return datetime.fromtimestamp(response.value)
        return datetime.utcnow()
    
    # ==================== Helper Methods ====================
    
    async def _get_token_decimals(self, token_address: str) -> int:
        """Get the decimals for an SPL token."""
        from solders.pubkey import Pubkey
        
        token_mint = Pubkey.from_string(token_address)
        response = await self._client.get_account_info(token_mint)
        
        if response.value is None:
            return 9  # Default to 9 decimals (like SOL)
        
        data = response.value.data
        return data[44] if len(data) > 44 else 9
    
    def _get_associated_token_address(self, owner, mint) -> 'Pubkey':
        """
        Derive the associated token account address.
        
        ATAs are deterministically derived from the owner and mint addresses.
        """
        from solders.pubkey import Pubkey
        from spl.token.constants import ASSOCIATED_TOKEN_PROGRAM_ID, TOKEN_PROGRAM_ID
        
        seeds = [
            bytes(owner),
            bytes(TOKEN_PROGRAM_ID),
            bytes(mint),
        ]
        
        ata, _ = Pubkey.find_program_address(seeds, ASSOCIATED_TOKEN_PROGRAM_ID)
        return ata
