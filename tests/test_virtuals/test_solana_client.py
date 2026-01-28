"""
Tests for the Solana Chain Client Implementation.

This module tests the concrete implementation of the chain client for Solana.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from forge.virtuals.chains.base_client import ChainClientError, TransactionFailedError
from forge.virtuals.chains.solana_client import SolanaChainClient
from forge.virtuals.config import ChainNetwork


# ==================== Fixtures ====================


@pytest.fixture
def mock_config():
    """Create a mock VirtualsConfig."""
    config = MagicMock()
    config.get_rpc_endpoint = MagicMock(return_value="https://api.mainnet-beta.solana.com")
    config.get_contract_address = MagicMock(return_value="7B8xLj" + "a" * 30)
    config.solana_private_key = None
    return config


@pytest.fixture
def mock_solana_client():
    """Create a mock Solana AsyncClient."""
    client = MagicMock()

    # Mock RPC responses
    client.get_latest_blockhash = AsyncMock(
        return_value=MagicMock(value=MagicMock(blockhash="mock_blockhash"))
    )
    client.get_balance = AsyncMock(
        return_value=MagicMock(value=1_000_000_000)  # 1 SOL in lamports
    )
    client.get_slot = AsyncMock(return_value=MagicMock(value=12345))
    client.get_block_time = AsyncMock(return_value=MagicMock(value=1700000000))
    client.get_account_info = AsyncMock(
        return_value=MagicMock(
            value=MagicMock(
                data=b"\x00" * 100,
                lamports=1_000_000_000,
                owner="TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
                executable=False,
                rent_epoch=0,
            )
        )
    )
    client.send_transaction = AsyncMock(
        return_value=MagicMock(value="mock_signature_" + "a" * 70)
    )
    client.get_signature_statuses = AsyncMock(
        return_value=MagicMock(
            value=[
                MagicMock(
                    err=None,
                    confirmation_status="confirmed",
                    slot=12345,
                )
            ]
        )
    )
    client.get_transaction = AsyncMock(
        return_value=MagicMock(
            value=MagicMock(
                slot=12345,
                block_time=1700000000,
                meta=MagicMock(err=None, compute_units_consumed=1000),
            )
        )
    )
    client.get_token_accounts_by_owner = AsyncMock(return_value=MagicMock(value=[]))
    client.close = AsyncMock()

    return client


@pytest.fixture
def solana_client(mock_config):
    """Create a SolanaChainClient for testing."""
    with patch("forge.virtuals.chains.solana_client.get_virtuals_config", return_value=mock_config):
        client = SolanaChainClient(ChainNetwork.SOLANA)
        return client


# ==================== Initialization Tests ====================


class TestSolanaClientInit:
    """Tests for SolanaChainClient initialization."""

    def test_init_creates_client(self, mock_config):
        """Test that initialization creates client with correct chain."""
        with patch("forge.virtuals.chains.solana_client.get_virtuals_config", return_value=mock_config):
            client = SolanaChainClient(ChainNetwork.SOLANA)

            assert client.chain == ChainNetwork.SOLANA
            assert client._initialized is False
            assert client._client is None

    def test_init_devnet(self, mock_config):
        """Test initialization for devnet."""
        with patch("forge.virtuals.chains.solana_client.get_virtuals_config", return_value=mock_config):
            client = SolanaChainClient(ChainNetwork.SOLANA_DEVNET)

            assert client.chain == ChainNetwork.SOLANA_DEVNET

    @pytest.mark.asyncio
    async def test_initialize_success(self, solana_client, mock_solana_client):
        """Test successful initialization."""
        with patch("forge.virtuals.chains.solana_client.AsyncClient", return_value=mock_solana_client):
            with patch("forge.virtuals.chains.solana_client.Keypair"):
                await solana_client.initialize()

                assert solana_client._initialized is True

    @pytest.mark.asyncio
    async def test_initialize_connection_failure(self, solana_client):
        """Test initialization with connection failure."""
        mock_client = MagicMock()
        mock_client.get_latest_blockhash = AsyncMock(
            return_value=MagicMock(value=None)
        )

        with patch("forge.virtuals.chains.solana_client.AsyncClient", return_value=mock_client):
            with pytest.raises(ChainClientError, match="Failed to connect"):
                await solana_client.initialize()

    @pytest.mark.asyncio
    async def test_initialize_import_error(self, solana_client):
        """Test initialization when Solana deps not installed."""
        with patch("forge.virtuals.chains.solana_client.AsyncClient", side_effect=ImportError):
            with pytest.raises(ChainClientError, match="dependencies not installed"):
                await solana_client.initialize()

    @pytest.mark.asyncio
    async def test_close(self, solana_client, mock_solana_client):
        """Test closing the client."""
        solana_client._client = mock_solana_client
        solana_client._initialized = True

        await solana_client.close()

        assert solana_client._initialized is False
        assert solana_client._client is None
        mock_solana_client.close.assert_called_once()


# ==================== Wallet Operations Tests ====================


class TestSolanaWalletOperations:
    """Tests for Solana wallet operations."""

    @pytest.mark.asyncio
    async def test_get_wallet_balance_sol(self, solana_client, mock_solana_client):
        """Test getting SOL balance."""
        solana_client._client = mock_solana_client
        solana_client._initialized = True

        with patch("forge.virtuals.chains.solana_client.Pubkey") as MockPubkey:
            MockPubkey.from_string = MagicMock()

            balance = await solana_client.get_wallet_balance("7B8xLj" + "a" * 30)

            assert balance == 1.0  # 1 SOL

    @pytest.mark.asyncio
    async def test_get_wallet_balance_not_initialized(self, solana_client):
        """Test getting balance when not initialized."""
        with pytest.raises(ChainClientError, match="not initialized"):
            await solana_client.get_wallet_balance("7B8xLj" + "a" * 30)

    @pytest.mark.asyncio
    async def test_get_virtual_balance(self, solana_client, mock_solana_client):
        """Test getting VIRTUAL token balance."""
        mock_solana_client.get_token_accounts_by_owner = AsyncMock(
            return_value=MagicMock(value=[])
        )
        solana_client._client = mock_solana_client
        solana_client._initialized = True

        with patch("forge.virtuals.chains.solana_client.Pubkey") as MockPubkey:
            MockPubkey.from_string = MagicMock()

            balance = await solana_client.get_virtual_balance("7B8xLj" + "a" * 30)

            assert balance == 0.0

    @pytest.mark.asyncio
    async def test_get_virtual_balance_no_address(self, solana_client, mock_solana_client):
        """Test getting VIRTUAL balance when address not configured."""
        solana_client._client = mock_solana_client
        solana_client._initialized = True
        solana_client.config.get_contract_address = MagicMock(return_value=None)

        with pytest.raises(ChainClientError, match="not configured"):
            await solana_client.get_virtual_balance("7B8xLj" + "a" * 30)

    @pytest.mark.asyncio
    async def test_create_wallet(self, solana_client, mock_solana_client):
        """Test creating a new wallet."""
        solana_client._client = mock_solana_client
        solana_client._initialized = True

        with patch("forge.virtuals.chains.solana_client.Keypair") as MockKeypair:
            mock_keypair = MagicMock()
            mock_keypair.pubkey.return_value = "mock_pubkey_" + "a" * 30
            MockKeypair.return_value = mock_keypair

            wallet_info, secret_key = await solana_client.create_wallet()

            assert wallet_info.chain == "solana"
            assert secret_key is not None


# ==================== Transaction Operations Tests ====================


class TestSolanaTransactionOperations:
    """Tests for Solana transaction operations."""

    @pytest.mark.asyncio
    async def test_send_transaction_no_keypair(self, solana_client, mock_solana_client):
        """Test sending transaction without keypair."""
        solana_client._client = mock_solana_client
        solana_client._initialized = True

        with pytest.raises(ChainClientError, match="No operator keypair"):
            await solana_client.send_transaction(
                to_address="7B8xLj" + "a" * 30,
                value=1.0,
            )

    @pytest.mark.asyncio
    async def test_send_transaction_negative_value(self, solana_client, mock_solana_client):
        """Test sending transaction with negative value."""
        solana_client._client = mock_solana_client
        solana_client._initialized = True
        solana_client._keypair = MagicMock()

        with pytest.raises(ValueError, match="cannot be negative"):
            await solana_client.send_transaction(
                to_address="7B8xLj" + "a" * 30,
                value=-1.0,
            )

    @pytest.mark.asyncio
    async def test_estimate_gas(self, solana_client, mock_solana_client):
        """Test gas estimation (compute units)."""
        solana_client._client = mock_solana_client
        solana_client._initialized = True

        gas = await solana_client.estimate_gas(
            to_address="7B8xLj" + "a" * 30,
            value=1.0,
        )

        assert gas == 200_000  # Default compute unit estimate

    @pytest.mark.asyncio
    async def test_get_current_block(self, solana_client, mock_solana_client):
        """Test getting current slot."""
        solana_client._client = mock_solana_client
        solana_client._initialized = True

        slot = await solana_client.get_current_block()

        assert slot == 12345

    @pytest.mark.asyncio
    async def test_get_block_timestamp(self, solana_client, mock_solana_client):
        """Test getting block timestamp."""
        solana_client._client = mock_solana_client
        solana_client._initialized = True

        timestamp = await solana_client.get_block_timestamp(12345)

        assert isinstance(timestamp, datetime)


# ==================== Token Operations Tests ====================


class TestSolanaTokenOperations:
    """Tests for Solana token operations."""

    @pytest.mark.asyncio
    async def test_transfer_tokens_no_keypair(self, solana_client, mock_solana_client):
        """Test token transfer without keypair."""
        solana_client._client = mock_solana_client
        solana_client._initialized = True

        with pytest.raises(ChainClientError, match="No operator keypair"):
            await solana_client.transfer_tokens(
                token_address="token" + "a" * 30,
                to_address="7B8xLj" + "a" * 30,
                amount=100.0,
            )

    @pytest.mark.asyncio
    async def test_approve_tokens_no_keypair(self, solana_client, mock_solana_client):
        """Test token approval without keypair."""
        solana_client._client = mock_solana_client
        solana_client._initialized = True

        with pytest.raises(ChainClientError, match="No operator keypair"):
            await solana_client.approve_tokens(
                token_address="token" + "a" * 30,
                spender_address="7B8xLj" + "a" * 30,
                amount=100.0,
            )

    @pytest.mark.asyncio
    async def test_get_token_info(self, solana_client, mock_solana_client):
        """Test getting token info."""
        # Mock account data with decimals at byte 44
        mock_data = b"\x00" * 44 + bytes([9]) + b"\x00" * 55
        mock_solana_client.get_account_info = AsyncMock(
            return_value=MagicMock(value=MagicMock(data=mock_data))
        )

        solana_client._client = mock_solana_client
        solana_client._initialized = True

        with patch("forge.virtuals.chains.solana_client.Pubkey") as MockPubkey:
            MockPubkey.from_string = MagicMock()

            info = await solana_client.get_token_info("token" + "a" * 30)

            assert info.chain == "solana"

    @pytest.mark.asyncio
    async def test_get_token_info_not_found(self, solana_client, mock_solana_client):
        """Test getting info for non-existent token."""
        mock_solana_client.get_account_info = AsyncMock(
            return_value=MagicMock(value=None)
        )
        solana_client._client = mock_solana_client
        solana_client._initialized = True

        with patch("forge.virtuals.chains.solana_client.Pubkey") as MockPubkey:
            MockPubkey.from_string = MagicMock()

            with pytest.raises(ChainClientError, match="not found"):
                await solana_client.get_token_info("token" + "a" * 30)


# ==================== Contract Operations Tests ====================


class TestSolanaContractOperations:
    """Tests for Solana program operations."""

    @pytest.mark.asyncio
    async def test_call_contract_balance(self, solana_client, mock_solana_client):
        """Test calling contract for balance query."""
        solana_client._client = mock_solana_client
        solana_client._initialized = True

        with patch("forge.virtuals.chains.solana_client.Pubkey") as MockPubkey:
            MockPubkey.from_string = MagicMock()

            result = await solana_client.call_contract(
                contract_address="account" + "a" * 30,
                function_name="balance",
                args=[],
            )

            assert result == 1.0  # 1 SOL

    @pytest.mark.asyncio
    async def test_call_contract_account_info(self, solana_client, mock_solana_client):
        """Test calling contract for account info."""
        solana_client._client = mock_solana_client
        solana_client._initialized = True

        with patch("forge.virtuals.chains.solana_client.Pubkey") as MockPubkey:
            MockPubkey.from_string = MagicMock()

            result = await solana_client.call_contract(
                contract_address="account" + "a" * 30,
                function_name="account_info",
                args=[],
            )

            assert "lamports" in result
            assert "owner" in result

    @pytest.mark.asyncio
    async def test_execute_contract_no_keypair(self, solana_client, mock_solana_client):
        """Test executing contract without keypair."""
        solana_client._client = mock_solana_client
        solana_client._initialized = True

        with pytest.raises(ChainClientError, match="No operator keypair"):
            await solana_client.execute_contract(
                contract_address="program" + "a" * 30,
                function_name="memo",
                args=["test memo"],
            )

    @pytest.mark.asyncio
    async def test_execute_contract_unknown_function(self, solana_client, mock_solana_client):
        """Test executing contract with unknown function."""
        solana_client._client = mock_solana_client
        solana_client._initialized = True
        solana_client._keypair = MagicMock()

        with pytest.raises(ChainClientError, match="Unknown instruction type"):
            await solana_client.execute_contract(
                contract_address="program" + "a" * 30,
                function_name="unknown_function",
                args=[],
            )


# ==================== Helper Methods Tests ====================


class TestSolanaHelperMethods:
    """Tests for Solana helper methods."""

    @pytest.mark.asyncio
    async def test_get_token_decimals(self, solana_client, mock_solana_client):
        """Test getting token decimals."""
        # Create mock data with decimals=9 at byte 44
        mock_data = b"\x00" * 44 + bytes([9]) + b"\x00" * 55
        mock_solana_client.get_account_info = AsyncMock(
            return_value=MagicMock(value=MagicMock(data=mock_data))
        )

        solana_client._client = mock_solana_client
        solana_client._initialized = True

        with patch("forge.virtuals.chains.solana_client.Pubkey") as MockPubkey:
            MockPubkey.from_string = MagicMock()

            decimals = await solana_client._get_token_decimals("token" + "a" * 30)

            assert decimals == 9

    @pytest.mark.asyncio
    async def test_get_token_decimals_default(self, solana_client, mock_solana_client):
        """Test getting token decimals with default when not found."""
        mock_solana_client.get_account_info = AsyncMock(
            return_value=MagicMock(value=None)
        )

        solana_client._client = mock_solana_client
        solana_client._initialized = True

        with patch("forge.virtuals.chains.solana_client.Pubkey") as MockPubkey:
            MockPubkey.from_string = MagicMock()

            decimals = await solana_client._get_token_decimals("token" + "a" * 30)

            assert decimals == 9  # Default
