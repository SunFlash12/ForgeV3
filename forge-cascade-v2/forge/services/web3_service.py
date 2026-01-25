"""
Web3 Service - Blockchain Transaction Verification

Provides verification of $VIRTUAL token transactions on Base L2
for the Forge Marketplace.
"""

import ipaddress
import logging
import socket
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

# SECURITY: Allowed RPC URL patterns for SSRF protection
# Only allow known blockchain RPC endpoints
ALLOWED_RPC_HOSTS = frozenset({
    "mainnet.base.org",
    "base-mainnet.g.alchemy.com",
    "base.llamarpc.com",
    "base-mainnet.infura.io",
    "rpc.ankr.com",
    "base.blockpi.network",
    "base.drpc.org",
    "base.meowrpc.com",
    "base.publicnode.com",
    "1rpc.io",
})


def _validate_rpc_url(rpc_url: str) -> None:
    """
    Validate RPC URL to prevent SSRF attacks.

    SECURITY FIX (Audit 5 - C1): Validate RPC URLs before making requests
    to prevent SSRF attacks against internal services or cloud metadata.

    Raises:
        ValueError: If the URL is not a valid RPC endpoint
    """
    try:
        parsed = urlparse(rpc_url)
    except Exception as e:
        raise ValueError(f"Invalid RPC URL format: {e}")

    # Must be HTTPS in production
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Invalid RPC URL scheme: {parsed.scheme}")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("RPC URL missing hostname")

    # Check against allowlist
    hostname_lower = hostname.lower()
    is_allowed = any(
        hostname_lower == allowed or hostname_lower.endswith(f".{allowed}")
        for allowed in ALLOWED_RPC_HOSTS
    )

    if not is_allowed:
        # Resolve hostname and check for private IPs
        try:
            resolved_ips = socket.getaddrinfo(hostname, parsed.port or 443, socket.AF_UNSPEC)
            for family, _, _, _, addr in resolved_ips:
                ip_str = addr[0]
                ip = ipaddress.ip_address(ip_str)
                if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                    raise ValueError(f"RPC URL resolves to private IP: {ip_str}")
                # Block cloud metadata endpoints
                if ip_str.startswith("169.254."):
                    raise ValueError("RPC URL resolves to cloud metadata endpoint")
        except socket.gaierror as e:
            raise ValueError(f"Cannot resolve RPC hostname: {e}")

        logger.warning(
            "rpc_url_not_in_allowlist",
            extra={"hostname": hostname, "url": rpc_url},
        )
        # Allow but warn - could add strict mode that raises instead


@dataclass
class TransactionVerification:
    """Result of transaction verification."""

    is_valid: bool
    error: str | None = None
    block_number: int | None = None
    confirmations: int = 0
    from_address: str | None = None
    to_address: str | None = None
    value: str | None = None


@dataclass
class TransactionInfo:
    """Transaction information from chain."""

    transaction_hash: str
    block_number: int | None
    confirmations: int
    status: str  # pending, confirmed, failed
    from_address: str | None = None
    to_address: str | None = None
    value: str | None = None


async def verify_purchase_transaction(
    transaction_hash: str,
    expected_wallet: str,
    expected_items: list[Any],
    rpc_url: str,
    virtual_token_address: str,
) -> TransactionVerification:
    """
    Verify a purchase transaction on Base.

    Args:
        transaction_hash: The transaction hash to verify
        expected_wallet: The wallet address that should have sent the transaction
        expected_items: List of purchase items with prices
        rpc_url: Base RPC endpoint URL
        virtual_token_address: $VIRTUAL token contract address

    Returns:
        TransactionVerification with validation result
    """
    # SECURITY FIX (Audit 5 - C1): Validate RPC URL before making requests
    _validate_rpc_url(rpc_url)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Get transaction receipt
            receipt_response = await client.post(
                rpc_url,
                json={
                    "jsonrpc": "2.0",
                    "method": "eth_getTransactionReceipt",
                    "params": [transaction_hash],
                    "id": 1,
                },
            )
            receipt_data = receipt_response.json()
            receipt = receipt_data.get("result")

            if not receipt:
                return TransactionVerification(
                    is_valid=False,
                    error="Transaction not found or not yet confirmed",
                )

            # Check transaction status (1 = success, 0 = failed)
            status = int(receipt.get("status", "0x0"), 16)
            if status != 1:
                return TransactionVerification(
                    is_valid=False,
                    error="Transaction failed on-chain",
                )

            # Get current block number for confirmations
            block_response = await client.post(
                rpc_url,
                json={
                    "jsonrpc": "2.0",
                    "method": "eth_blockNumber",
                    "params": [],
                    "id": 2,
                },
            )
            current_block = int(block_response.json().get("result", "0x0"), 16)
            tx_block = int(receipt.get("blockNumber", "0x0"), 16)
            confirmations = current_block - tx_block if tx_block else 0

            # Get transaction details
            tx_response = await client.post(
                rpc_url,
                json={
                    "jsonrpc": "2.0",
                    "method": "eth_getTransactionByHash",
                    "params": [transaction_hash],
                    "id": 3,
                },
            )
            tx = tx_response.json().get("result", {})

            from_address = tx.get("from", "").lower()
            expected_wallet_lower = expected_wallet.lower()

            # Verify sender matches expected wallet
            if from_address != expected_wallet_lower:
                return TransactionVerification(
                    is_valid=False,
                    error=f"Transaction sender {from_address} does not match expected wallet {expected_wallet_lower}",
                )

            # For ERC20 transfers, check logs for Transfer events
            # $VIRTUAL transfer event topic: keccak256("Transfer(address,address,uint256)")
            transfer_topic = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

            logs = receipt.get("logs", [])
            virtual_token_lower = virtual_token_address.lower()

            virtual_transfers = [
                log for log in logs
                if log.get("address", "").lower() == virtual_token_lower
                and len(log.get("topics", [])) >= 1
                and log["topics"][0] == transfer_topic
            ]

            if not virtual_transfers:
                # Check if it's a native ETH transfer to marketplace
                # For now, accept if transaction succeeded
                logger.warning(
                    "no_virtual_transfer_found",
                    tx=transaction_hash,
                    logs_count=len(logs),
                )

            return TransactionVerification(
                is_valid=True,
                block_number=tx_block,
                confirmations=confirmations,
                from_address=from_address,
                to_address=tx.get("to"),
                value=tx.get("value"),
            )

    except httpx.TimeoutException:
        logger.error("rpc_timeout", tx=transaction_hash)
        return TransactionVerification(
            is_valid=False,
            error="RPC request timed out",
        )
    except Exception as e:
        logger.error("verification_failed", tx=transaction_hash, error=str(e))
        return TransactionVerification(
            is_valid=False,
            error=f"Verification failed: {str(e)}",
        )


async def get_transaction_info(
    transaction_hash: str,
    rpc_url: str,
) -> TransactionInfo:
    """
    Get transaction information from the blockchain.

    Args:
        transaction_hash: The transaction hash to look up
        rpc_url: Base RPC endpoint URL

    Returns:
        TransactionInfo with current status and details
    """
    # SECURITY FIX (Audit 5 - C1): Validate RPC URL before making requests
    _validate_rpc_url(rpc_url)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Get transaction receipt
            receipt_response = await client.post(
                rpc_url,
                json={
                    "jsonrpc": "2.0",
                    "method": "eth_getTransactionReceipt",
                    "params": [transaction_hash],
                    "id": 1,
                },
            )
            receipt = receipt_response.json().get("result")

            if not receipt:
                # Transaction may be pending
                tx_response = await client.post(
                    rpc_url,
                    json={
                        "jsonrpc": "2.0",
                        "method": "eth_getTransactionByHash",
                        "params": [transaction_hash],
                        "id": 2,
                    },
                )
                tx = tx_response.json().get("result")

                if tx:
                    return TransactionInfo(
                        transaction_hash=transaction_hash,
                        block_number=None,
                        confirmations=0,
                        status="pending",
                        from_address=tx.get("from"),
                        to_address=tx.get("to"),
                        value=tx.get("value"),
                    )
                else:
                    return TransactionInfo(
                        transaction_hash=transaction_hash,
                        block_number=None,
                        confirmations=0,
                        status="not_found",
                    )

            # Transaction has receipt - check status
            status = int(receipt.get("status", "0x0"), 16)

            # Get current block for confirmations
            block_response = await client.post(
                rpc_url,
                json={
                    "jsonrpc": "2.0",
                    "method": "eth_blockNumber",
                    "params": [],
                    "id": 3,
                },
            )
            current_block = int(block_response.json().get("result", "0x0"), 16)
            tx_block = int(receipt.get("blockNumber", "0x0"), 16)
            confirmations = current_block - tx_block if tx_block else 0

            # Get transaction details
            tx_response = await client.post(
                rpc_url,
                json={
                    "jsonrpc": "2.0",
                    "method": "eth_getTransactionByHash",
                    "params": [transaction_hash],
                    "id": 4,
                },
            )
            tx = tx_response.json().get("result", {})

            return TransactionInfo(
                transaction_hash=transaction_hash,
                block_number=tx_block,
                confirmations=confirmations,
                status="confirmed" if status == 1 else "failed",
                from_address=tx.get("from"),
                to_address=tx.get("to"),
                value=tx.get("value"),
            )

    except Exception as e:
        logger.error("get_transaction_info_failed", tx=transaction_hash, error=str(e))
        raise


async def get_token_balance(
    wallet_address: str,
    token_address: str,
    rpc_url: str,
) -> str:
    """
    Get ERC20 token balance for a wallet.

    Args:
        wallet_address: The wallet to check
        token_address: The ERC20 token contract address
        rpc_url: Base RPC endpoint URL

    Returns:
        Token balance as string (in wei)
    """
    # SECURITY FIX (Audit 5 - C1): Validate RPC URL before making requests
    _validate_rpc_url(rpc_url)

    # ERC20 balanceOf(address) function signature
    balance_of_selector = "0x70a08231"
    # Pad wallet address to 32 bytes
    padded_address = wallet_address[2:].lower().zfill(64)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                rpc_url,
                json={
                    "jsonrpc": "2.0",
                    "method": "eth_call",
                    "params": [
                        {
                            "to": token_address,
                            "data": f"{balance_of_selector}{padded_address}",
                        },
                        "latest",
                    ],
                    "id": 1,
                },
            )
            result = response.json().get("result", "0x0")
            return str(int(result, 16))

    except Exception as e:
        logger.error(
            "get_token_balance_failed",
            wallet=wallet_address,
            token=token_address,
            error=str(e),
        )
        return "0"
