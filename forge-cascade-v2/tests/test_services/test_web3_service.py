"""
Tests for Web3 Service - Blockchain Transaction Verification

Tests the verification of $VIRTUAL token transactions on Base L2
for the Forge Marketplace.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from forge.services.web3_service import (
    ALLOWED_RPC_HOSTS,
    TransactionInfo,
    TransactionVerification,
    _validate_rpc_url,
    get_token_balance,
    get_transaction_info,
    verify_purchase_transaction,
)


# =============================================================================
# Test Constants
# =============================================================================


class TestConstants:
    """Tests for module constants."""

    def test_allowed_rpc_hosts_not_empty(self):
        """Test that allowed RPC hosts list is not empty."""
        assert len(ALLOWED_RPC_HOSTS) > 0

    def test_allowed_rpc_hosts_contains_base(self):
        """Test that allowed hosts contains Base mainnet."""
        assert "mainnet.base.org" in ALLOWED_RPC_HOSTS

    def test_allowed_rpc_hosts_is_frozen(self):
        """Test that allowed hosts is immutable."""
        assert isinstance(ALLOWED_RPC_HOSTS, frozenset)


# =============================================================================
# Test TransactionVerification Dataclass
# =============================================================================


class TestTransactionVerification:
    """Tests for TransactionVerification dataclass."""

    def test_valid_transaction(self):
        """Test valid transaction verification."""
        verification = TransactionVerification(
            is_valid=True,
            block_number=12345678,
            confirmations=10,
            from_address="0xSender...",
            to_address="0xReceiver...",
            value="1000000000000000000",
        )

        assert verification.is_valid is True
        assert verification.error is None
        assert verification.block_number == 12345678
        assert verification.confirmations == 10

    def test_invalid_transaction(self):
        """Test invalid transaction verification."""
        verification = TransactionVerification(
            is_valid=False,
            error="Transaction not found",
        )

        assert verification.is_valid is False
        assert verification.error == "Transaction not found"

    def test_default_values(self):
        """Test default values for TransactionVerification."""
        verification = TransactionVerification(is_valid=True)

        assert verification.error is None
        assert verification.block_number is None
        assert verification.confirmations == 0
        assert verification.from_address is None
        assert verification.to_address is None
        assert verification.value is None


# =============================================================================
# Test TransactionInfo Dataclass
# =============================================================================


class TestTransactionInfo:
    """Tests for TransactionInfo dataclass."""

    def test_confirmed_transaction(self):
        """Test confirmed transaction info."""
        info = TransactionInfo(
            transaction_hash="0xabc123...",
            block_number=12345678,
            confirmations=15,
            status="confirmed",
            from_address="0xSender...",
            to_address="0xReceiver...",
            value="1000000000000000000",
        )

        assert info.status == "confirmed"
        assert info.block_number == 12345678
        assert info.confirmations == 15

    def test_pending_transaction(self):
        """Test pending transaction info."""
        info = TransactionInfo(
            transaction_hash="0xdef456...",
            block_number=None,
            confirmations=0,
            status="pending",
        )

        assert info.status == "pending"
        assert info.block_number is None
        assert info.confirmations == 0

    def test_failed_transaction(self):
        """Test failed transaction info."""
        info = TransactionInfo(
            transaction_hash="0xfail...",
            block_number=12345678,
            confirmations=10,
            status="failed",
        )

        assert info.status == "failed"

    def test_not_found_transaction(self):
        """Test not found transaction info."""
        info = TransactionInfo(
            transaction_hash="0xnotfound...",
            block_number=None,
            confirmations=0,
            status="not_found",
        )

        assert info.status == "not_found"


# =============================================================================
# Test _validate_rpc_url
# =============================================================================


class TestValidateRpcUrl:
    """Tests for _validate_rpc_url function."""

    def test_valid_https_allowed_host(self):
        """Test valid HTTPS URL with allowed host."""
        # Should not raise
        _validate_rpc_url("https://mainnet.base.org")

    def test_valid_http_allowed_host(self):
        """Test valid HTTP URL with allowed host."""
        # Should not raise (HTTP is allowed but less secure)
        _validate_rpc_url("http://mainnet.base.org")

    def test_valid_subdomain_allowed_host(self):
        """Test valid URL with subdomain of allowed host."""
        # Should not raise
        _validate_rpc_url("https://v2.mainnet.base.org")

    def test_invalid_scheme(self):
        """Test invalid URL scheme raises error."""
        with pytest.raises(ValueError, match="Invalid RPC URL scheme"):
            _validate_rpc_url("ftp://mainnet.base.org")

    def test_missing_hostname(self):
        """Test URL without hostname raises error."""
        with pytest.raises(ValueError, match="missing hostname"):
            _validate_rpc_url("https:///path")

    def test_private_ip_rejected(self):
        """Test that private IP addresses are rejected."""
        with patch("socket.getaddrinfo") as mock_getaddrinfo:
            mock_getaddrinfo.return_value = [
                (2, 1, 6, "", ("192.168.1.1", 443)),
            ]

            with pytest.raises(ValueError, match="private IP"):
                _validate_rpc_url("https://private-rpc.example.com")

    def test_loopback_ip_rejected(self):
        """Test that loopback addresses are rejected."""
        with patch("socket.getaddrinfo") as mock_getaddrinfo:
            mock_getaddrinfo.return_value = [
                (2, 1, 6, "", ("127.0.0.1", 443)),
            ]

            with pytest.raises(ValueError, match="private IP"):
                _validate_rpc_url("https://localhost-rpc.example.com")

    def test_cloud_metadata_endpoint_rejected(self):
        """Test that cloud metadata endpoints are rejected."""
        with patch("socket.getaddrinfo") as mock_getaddrinfo:
            mock_getaddrinfo.return_value = [
                (2, 1, 6, "", ("169.254.169.254", 443)),
            ]

            with pytest.raises(ValueError, match="(private IP|cloud metadata)"):
                _validate_rpc_url("https://metadata.example.com")

    def test_dns_resolution_failure(self):
        """Test handling of DNS resolution failure."""
        import socket

        with patch("socket.getaddrinfo") as mock_getaddrinfo:
            mock_getaddrinfo.side_effect = socket.gaierror("DNS resolution failed")

            with pytest.raises(ValueError, match="Cannot resolve"):
                _validate_rpc_url("https://nonexistent.example.com")

    def test_unallowed_host_with_public_ip_warns(self):
        """Test that unallowed host with public IP logs warning but passes."""
        with patch("socket.getaddrinfo") as mock_getaddrinfo:
            mock_getaddrinfo.return_value = [
                (2, 1, 6, "", ("8.8.8.8", 443)),  # Public IP
            ]

            # Should not raise, just log a warning
            _validate_rpc_url("https://unknown-rpc.example.com")


# =============================================================================
# Test verify_purchase_transaction
# =============================================================================


class TestVerifyPurchaseTransaction:
    """Tests for verify_purchase_transaction function."""

    @pytest.fixture
    def mock_httpx_client(self):
        """Create a mock httpx client."""
        client = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_successful_verification(self):
        """Test successful transaction verification."""
        mock_response_receipt = MagicMock()
        mock_response_receipt.json.return_value = {
            "result": {
                "status": "0x1",  # Success
                "blockNumber": "0xBC614E",  # 12345678
                "logs": [
                    {
                        "address": "0x0b3e328455c4059eeb9e3f84b5543f74e24e7e1b",
                        "topics": [
                            "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
                        ],
                    }
                ],
            }
        }

        mock_response_block = MagicMock()
        mock_response_block.json.return_value = {"result": "0xBC6162"}  # 12345698

        mock_response_tx = MagicMock()
        mock_response_tx.json.return_value = {
            "result": {
                "from": "0xwallet123",
                "to": "0xreceiver",
                "value": "0xDE0B6B3A7640000",
            }
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(
                side_effect=[mock_response_receipt, mock_response_block, mock_response_tx]
            )
            mock_client_class.return_value = mock_client

            result = await verify_purchase_transaction(
                transaction_hash="0xabc123",
                expected_wallet="0xwallet123",
                expected_items=[],
                rpc_url="https://mainnet.base.org",
                virtual_token_address="0x0b3e328455c4059EEb9e3f84b5543F74E24e7E1b",
            )

        assert result.is_valid is True
        assert result.block_number == 12345678

    @pytest.mark.asyncio
    async def test_transaction_not_found(self):
        """Test verification when transaction not found."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": None}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await verify_purchase_transaction(
                transaction_hash="0xnotfound",
                expected_wallet="0xwallet123",
                expected_items=[],
                rpc_url="https://mainnet.base.org",
                virtual_token_address="0x0b3e328455c4059EEb9e3f84b5543F74E24e7E1b",
            )

        assert result.is_valid is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_failed_transaction(self):
        """Test verification of failed transaction."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {
                "status": "0x0",  # Failed
                "blockNumber": "0xBC614E",
                "logs": [],
            }
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await verify_purchase_transaction(
                transaction_hash="0xfailed",
                expected_wallet="0xwallet123",
                expected_items=[],
                rpc_url="https://mainnet.base.org",
                virtual_token_address="0x0b3e328455c4059EEb9e3f84b5543F74E24e7E1b",
            )

        assert result.is_valid is False
        assert "failed" in result.error.lower()

    @pytest.mark.asyncio
    async def test_wallet_mismatch(self):
        """Test verification when sender doesn't match expected wallet."""
        mock_response_receipt = MagicMock()
        mock_response_receipt.json.return_value = {
            "result": {
                "status": "0x1",
                "blockNumber": "0xBC614E",
                "logs": [],
            }
        }

        mock_response_block = MagicMock()
        mock_response_block.json.return_value = {"result": "0xBC6162"}

        mock_response_tx = MagicMock()
        mock_response_tx.json.return_value = {
            "result": {
                "from": "0xdifferentwallet",  # Different from expected
                "to": "0xreceiver",
                "value": "0xDE0B6B3A7640000",
            }
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(
                side_effect=[mock_response_receipt, mock_response_block, mock_response_tx]
            )
            mock_client_class.return_value = mock_client

            result = await verify_purchase_transaction(
                transaction_hash="0xabc123",
                expected_wallet="0xwallet123",
                expected_items=[],
                rpc_url="https://mainnet.base.org",
                virtual_token_address="0x0b3e328455c4059EEb9e3f84b5543F74E24e7E1b",
            )

        assert result.is_valid is False
        assert "does not match" in result.error

    @pytest.mark.asyncio
    async def test_rpc_timeout(self):
        """Test handling of RPC timeout."""
        import httpx

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
            mock_client_class.return_value = mock_client

            result = await verify_purchase_transaction(
                transaction_hash="0xabc123",
                expected_wallet="0xwallet123",
                expected_items=[],
                rpc_url="https://mainnet.base.org",
                virtual_token_address="0x0b3e328455c4059EEb9e3f84b5543F74E24e7E1b",
            )

        assert result.is_valid is False
        assert "timed out" in result.error.lower()

    @pytest.mark.asyncio
    async def test_invalid_rpc_url(self):
        """Test verification with invalid RPC URL."""
        result = await verify_purchase_transaction(
            transaction_hash="0xabc123",
            expected_wallet="0xwallet123",
            expected_items=[],
            rpc_url="https://localhost:8545",  # Invalid - private
            virtual_token_address="0x0b3e328455c4059EEb9e3f84b5543F74E24e7E1b",
        )

        assert result.is_valid is False


# =============================================================================
# Test get_transaction_info
# =============================================================================


class TestGetTransactionInfo:
    """Tests for get_transaction_info function."""

    @pytest.mark.asyncio
    async def test_confirmed_transaction(self):
        """Test getting info for confirmed transaction."""
        mock_response_receipt = MagicMock()
        mock_response_receipt.json.return_value = {
            "result": {
                "status": "0x1",
                "blockNumber": "0xBC614E",
            }
        }

        mock_response_block = MagicMock()
        mock_response_block.json.return_value = {"result": "0xBC6162"}

        mock_response_tx = MagicMock()
        mock_response_tx.json.return_value = {
            "result": {
                "from": "0xsender",
                "to": "0xreceiver",
                "value": "0xDE0B6B3A7640000",
            }
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(
                side_effect=[mock_response_receipt, mock_response_block, mock_response_tx]
            )
            mock_client_class.return_value = mock_client

            result = await get_transaction_info(
                transaction_hash="0xabc123",
                rpc_url="https://mainnet.base.org",
            )

        assert result.status == "confirmed"
        assert result.block_number == 12345678

    @pytest.mark.asyncio
    async def test_pending_transaction(self):
        """Test getting info for pending transaction."""
        mock_response_receipt = MagicMock()
        mock_response_receipt.json.return_value = {"result": None}  # No receipt yet

        mock_response_tx = MagicMock()
        mock_response_tx.json.return_value = {
            "result": {
                "from": "0xsender",
                "to": "0xreceiver",
                "value": "0xDE0B6B3A7640000",
            }
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(
                side_effect=[mock_response_receipt, mock_response_tx]
            )
            mock_client_class.return_value = mock_client

            result = await get_transaction_info(
                transaction_hash="0xpending",
                rpc_url="https://mainnet.base.org",
            )

        assert result.status == "pending"
        assert result.block_number is None
        assert result.confirmations == 0

    @pytest.mark.asyncio
    async def test_not_found_transaction(self):
        """Test getting info for non-existent transaction."""
        mock_response_receipt = MagicMock()
        mock_response_receipt.json.return_value = {"result": None}

        mock_response_tx = MagicMock()
        mock_response_tx.json.return_value = {"result": None}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(
                side_effect=[mock_response_receipt, mock_response_tx]
            )
            mock_client_class.return_value = mock_client

            result = await get_transaction_info(
                transaction_hash="0xnotfound",
                rpc_url="https://mainnet.base.org",
            )

        assert result.status == "not_found"

    @pytest.mark.asyncio
    async def test_failed_transaction(self):
        """Test getting info for failed transaction."""
        mock_response_receipt = MagicMock()
        mock_response_receipt.json.return_value = {
            "result": {
                "status": "0x0",  # Failed
                "blockNumber": "0xBC614E",
            }
        }

        mock_response_block = MagicMock()
        mock_response_block.json.return_value = {"result": "0xBC6162"}

        mock_response_tx = MagicMock()
        mock_response_tx.json.return_value = {
            "result": {
                "from": "0xsender",
                "to": "0xreceiver",
                "value": "0x0",
            }
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(
                side_effect=[mock_response_receipt, mock_response_block, mock_response_tx]
            )
            mock_client_class.return_value = mock_client

            result = await get_transaction_info(
                transaction_hash="0xfailed",
                rpc_url="https://mainnet.base.org",
            )

        assert result.status == "failed"

    @pytest.mark.asyncio
    async def test_raises_on_error(self):
        """Test that errors are propagated."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(side_effect=RuntimeError("Network error"))
            mock_client_class.return_value = mock_client

            with pytest.raises(RuntimeError):
                await get_transaction_info(
                    transaction_hash="0xabc123",
                    rpc_url="https://mainnet.base.org",
                )


# =============================================================================
# Test get_token_balance
# =============================================================================


class TestGetTokenBalance:
    """Tests for get_token_balance function."""

    @pytest.mark.asyncio
    async def test_successful_balance(self):
        """Test successful balance retrieval."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": "0xDE0B6B3A7640000"  # 1 ETH in wei
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await get_token_balance(
                wallet_address="0xwallet123",
                token_address="0x0b3e328455c4059EEb9e3f84b5543F74E24e7E1b",
                rpc_url="https://mainnet.base.org",
            )

        assert result == str(10**18)  # 1 ETH in wei

    @pytest.mark.asyncio
    async def test_zero_balance(self):
        """Test zero balance retrieval."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": "0x0"}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await get_token_balance(
                wallet_address="0xemptywallet",
                token_address="0x0b3e328455c4059EEb9e3f84b5543F74E24e7E1b",
                rpc_url="https://mainnet.base.org",
            )

        assert result == "0"

    @pytest.mark.asyncio
    async def test_error_returns_zero(self):
        """Test that errors return zero balance."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(side_effect=RuntimeError("Network error"))
            mock_client_class.return_value = mock_client

            result = await get_token_balance(
                wallet_address="0xwallet123",
                token_address="0x0b3e328455c4059EEb9e3f84b5543F74E24e7E1b",
                rpc_url="https://mainnet.base.org",
            )

        assert result == "0"

    @pytest.mark.asyncio
    async def test_correct_eth_call_data(self):
        """Test that the correct eth_call data is sent."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": "0x100"}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            await get_token_balance(
                wallet_address="0x742d35Cc6634C0532925a3b844Bc9e7595f5",
                token_address="0x0b3e328455c4059EEb9e3f84b5543F74E24e7E1b",
                rpc_url="https://mainnet.base.org",
            )

            # Verify the call was made with correct parameters
            call_args = mock_client.post.call_args
            json_data = call_args.kwargs["json"]

            assert json_data["method"] == "eth_call"
            assert json_data["params"][0]["to"] == "0x0b3e328455c4059EEb9e3f84b5543F74E24e7E1b"
            # balanceOf selector
            assert json_data["params"][0]["data"].startswith("0x70a08231")


# =============================================================================
# Test Confirmations Calculation
# =============================================================================


class TestConfirmationsCalculation:
    """Tests for transaction confirmation calculations."""

    @pytest.mark.asyncio
    async def test_confirmations_calculated_correctly(self):
        """Test that confirmations are calculated correctly."""
        mock_response_receipt = MagicMock()
        mock_response_receipt.json.return_value = {
            "result": {
                "status": "0x1",
                "blockNumber": "0x64",  # 100
                "logs": [],
            }
        }

        mock_response_block = MagicMock()
        mock_response_block.json.return_value = {"result": "0x69"}  # 105

        mock_response_tx = MagicMock()
        mock_response_tx.json.return_value = {
            "result": {
                "from": "0xwallet123",
                "to": "0xreceiver",
                "value": "0x0",
            }
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(
                side_effect=[mock_response_receipt, mock_response_block, mock_response_tx]
            )
            mock_client_class.return_value = mock_client

            result = await verify_purchase_transaction(
                transaction_hash="0xabc123",
                expected_wallet="0xwallet123",
                expected_items=[],
                rpc_url="https://mainnet.base.org",
                virtual_token_address="0x0b3e328455c4059EEb9e3f84b5543F74E24e7E1b",
            )

        # 105 - 100 = 5 confirmations
        assert result.confirmations == 5


# =============================================================================
# Test VIRTUAL Token Transfer Detection
# =============================================================================


class TestVirtualTokenTransferDetection:
    """Tests for VIRTUAL token transfer detection in transaction logs."""

    @pytest.mark.asyncio
    async def test_virtual_transfer_detected(self):
        """Test detection of VIRTUAL token Transfer event."""
        transfer_topic = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

        mock_response_receipt = MagicMock()
        mock_response_receipt.json.return_value = {
            "result": {
                "status": "0x1",
                "blockNumber": "0xBC614E",
                "logs": [
                    {
                        "address": "0x0b3e328455c4059eeb9e3f84b5543f74e24e7e1b",  # VIRTUAL token
                        "topics": [
                            transfer_topic,
                            "0x000000000000000000000000sender",
                            "0x000000000000000000000000receiver",
                        ],
                        "data": "0x0000000000000000000000000000000000000000000000000de0b6b3a7640000",
                    },
                    {
                        "address": "0xothercontract",  # Other contract
                        "topics": ["0xotherevent"],
                    },
                ],
            }
        }

        mock_response_block = MagicMock()
        mock_response_block.json.return_value = {"result": "0xBC6162"}

        mock_response_tx = MagicMock()
        mock_response_tx.json.return_value = {
            "result": {
                "from": "0xwallet123",
                "to": "0xreceiver",
                "value": "0x0",
            }
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(
                side_effect=[mock_response_receipt, mock_response_block, mock_response_tx]
            )
            mock_client_class.return_value = mock_client

            result = await verify_purchase_transaction(
                transaction_hash="0xabc123",
                expected_wallet="0xwallet123",
                expected_items=[],
                rpc_url="https://mainnet.base.org",
                virtual_token_address="0x0b3e328455c4059EEb9e3f84b5543F74E24e7E1b",
            )

        assert result.is_valid is True

    @pytest.mark.asyncio
    async def test_no_virtual_transfer_logs_warning(self):
        """Test warning when no VIRTUAL transfer is found."""
        mock_response_receipt = MagicMock()
        mock_response_receipt.json.return_value = {
            "result": {
                "status": "0x1",
                "blockNumber": "0xBC614E",
                "logs": [
                    {
                        "address": "0xothercontract",  # Not VIRTUAL token
                        "topics": ["0xotherevent"],
                    },
                ],
            }
        }

        mock_response_block = MagicMock()
        mock_response_block.json.return_value = {"result": "0xBC6162"}

        mock_response_tx = MagicMock()
        mock_response_tx.json.return_value = {
            "result": {
                "from": "0xwallet123",
                "to": "0xreceiver",
                "value": "0xDE0B6B3A7640000",  # Native ETH transfer
            }
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(
                side_effect=[mock_response_receipt, mock_response_block, mock_response_tx]
            )
            mock_client_class.return_value = mock_client

            # Should still pass (native ETH transfer)
            result = await verify_purchase_transaction(
                transaction_hash="0xabc123",
                expected_wallet="0xwallet123",
                expected_items=[],
                rpc_url="https://mainnet.base.org",
                virtual_token_address="0x0b3e328455c4059EEb9e3f84b5543F74E24e7E1b",
            )

        # Transaction is still valid (could be native ETH)
        assert result.is_valid is True


# =============================================================================
# Test Case Insensitive Address Comparison
# =============================================================================


class TestCaseInsensitiveAddressComparison:
    """Tests for case-insensitive address comparison."""

    @pytest.mark.asyncio
    async def test_address_comparison_case_insensitive(self):
        """Test that address comparison is case-insensitive."""
        mock_response_receipt = MagicMock()
        mock_response_receipt.json.return_value = {
            "result": {
                "status": "0x1",
                "blockNumber": "0xBC614E",
                "logs": [],
            }
        }

        mock_response_block = MagicMock()
        mock_response_block.json.return_value = {"result": "0xBC6162"}

        mock_response_tx = MagicMock()
        mock_response_tx.json.return_value = {
            "result": {
                "from": "0xWALLET123ABC",  # Uppercase
                "to": "0xreceiver",
                "value": "0x0",
            }
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(
                side_effect=[mock_response_receipt, mock_response_block, mock_response_tx]
            )
            mock_client_class.return_value = mock_client

            result = await verify_purchase_transaction(
                transaction_hash="0xabc123",
                expected_wallet="0xwallet123abc",  # Lowercase
                expected_items=[],
                rpc_url="https://mainnet.base.org",
                virtual_token_address="0x0b3e328455c4059EEb9e3f84b5543F74E24e7E1b",
            )

        # Should match despite case difference
        assert result.is_valid is True
