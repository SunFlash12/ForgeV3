"""
Tests for the EVM Chain Client Implementation.

This module tests the concrete implementation of the chain client
for EVM-compatible chains (Base, Ethereum).
"""

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from forge.virtuals.chains.base_client import ChainClientError, TransactionFailedError
from forge.virtuals.chains.evm_client import ERC20_ABI, EVMChainClient
from forge.virtuals.config import ChainNetwork


# ==================== Fixtures ====================


@pytest.fixture
def mock_config():
    """Create a mock VirtualsConfig."""
    config = MagicMock()
    config.get_rpc_endpoint = MagicMock(return_value="https://rpc.example.com")
    config.get_contract_address = MagicMock(return_value="0x" + "1" * 40)
    config.operator_private_key = None
    return config


@pytest.fixture
def mock_web3():
    """Create a mock AsyncWeb3 instance."""
    mock_w3 = MagicMock()

    # Mock eth attribute
    mock_eth = MagicMock()
    mock_eth.chain_id = AsyncMock(return_value=8453)  # Base chain ID
    mock_eth.get_balance = AsyncMock(return_value=10**18)  # 1 ETH in wei
    mock_eth.get_transaction_count = AsyncMock(return_value=5)
    mock_eth.get_block = AsyncMock(return_value={"baseFeePerGas": 10**9, "timestamp": 1700000000})
    mock_eth.max_priority_fee = AsyncMock(return_value=10**8)
    mock_eth.estimate_gas = AsyncMock(return_value=21000)
    mock_eth.send_raw_transaction = AsyncMock(return_value=b"\x00" * 32)
    mock_eth.get_transaction_receipt = AsyncMock(return_value={"status": 1, "blockNumber": 12345, "gasUsed": 21000})
    mock_eth.get_transaction = AsyncMock(return_value={"from": "0x1", "to": "0x2", "value": 0})
    mock_eth.block_number = AsyncMock(return_value=12345)

    # Mock contract creation
    mock_contract = MagicMock()
    mock_contract.functions = MagicMock()
    mock_eth.contract = MagicMock(return_value=mock_contract)

    mock_w3.eth = mock_eth
    mock_w3.to_checksum_address = MagicMock(side_effect=lambda x: x)
    mock_w3.from_wei = MagicMock(side_effect=lambda x, unit: x / 10**18)
    mock_w3.to_wei = MagicMock(side_effect=lambda x, unit: int(x * 10**18))

    return mock_w3


@pytest.fixture
def evm_client(mock_config):
    """Create an EVMChainClient for testing."""
    with patch("forge.virtuals.chains.evm_client.get_virtuals_config", return_value=mock_config):
        client = EVMChainClient(ChainNetwork.BASE)
        return client


# ==================== Initialization Tests ====================


class TestEVMClientInit:
    """Tests for EVMChainClient initialization."""

    def test_init_creates_client(self, mock_config):
        """Test that initialization creates client with correct chain."""
        with patch("forge.virtuals.chains.evm_client.get_virtuals_config", return_value=mock_config):
            client = EVMChainClient(ChainNetwork.BASE)

            assert client.chain == ChainNetwork.BASE
            assert client._initialized is False
            assert client._w3 is None

    @pytest.mark.asyncio
    async def test_initialize_success(self, evm_client, mock_web3):
        """Test successful initialization."""
        with patch("forge.virtuals.chains.evm_client.AsyncWeb3", return_value=mock_web3):
            with patch("forge.virtuals.chains.evm_client.AsyncHTTPProvider"):
                await evm_client.initialize()

                assert evm_client._initialized is True
                assert evm_client._w3 is not None

    @pytest.mark.asyncio
    async def test_initialize_connection_error(self, evm_client):
        """Test initialization with connection error."""
        mock_w3 = MagicMock()
        mock_w3.eth.chain_id = AsyncMock(side_effect=ConnectionError("Cannot connect"))

        with patch("forge.virtuals.chains.evm_client.AsyncWeb3", return_value=mock_w3):
            with patch("forge.virtuals.chains.evm_client.AsyncHTTPProvider"):
                with pytest.raises(ChainClientError, match="Failed to connect"):
                    await evm_client.initialize()

    @pytest.mark.asyncio
    async def test_close(self, evm_client, mock_web3):
        """Test closing the client."""
        mock_web3.provider = MagicMock()
        mock_web3.provider.disconnect = AsyncMock()

        with patch("forge.virtuals.chains.evm_client.AsyncWeb3", return_value=mock_web3):
            with patch("forge.virtuals.chains.evm_client.AsyncHTTPProvider"):
                await evm_client.initialize()
                await evm_client.close()

                assert evm_client._initialized is False
                assert evm_client._w3 is None


# ==================== Wallet Operations Tests ====================


class TestWalletOperations:
    """Tests for wallet operations."""

    @pytest.mark.asyncio
    async def test_get_wallet_balance_native(self, evm_client, mock_web3):
        """Test getting native currency balance."""
        with patch("forge.virtuals.chains.evm_client.AsyncWeb3", return_value=mock_web3):
            with patch("forge.virtuals.chains.evm_client.AsyncHTTPProvider"):
                await evm_client.initialize()

                balance = await evm_client.get_wallet_balance("0x" + "1" * 40)

                assert balance == 1.0  # 1 ETH

    @pytest.mark.asyncio
    async def test_get_wallet_balance_not_initialized(self, evm_client):
        """Test getting balance when not initialized."""
        with pytest.raises(ChainClientError, match="not initialized"):
            await evm_client.get_wallet_balance("0x" + "1" * 40)

    @pytest.mark.asyncio
    async def test_get_virtual_balance(self, evm_client, mock_web3):
        """Test getting VIRTUAL token balance."""
        mock_contract = MagicMock()
        mock_contract.functions.balanceOf = MagicMock(
            return_value=MagicMock(call=AsyncMock(return_value=100 * 10**18))
        )
        mock_contract.functions.decimals = MagicMock(
            return_value=MagicMock(call=AsyncMock(return_value=18))
        )
        mock_web3.eth.contract = MagicMock(return_value=mock_contract)

        with patch("forge.virtuals.chains.evm_client.AsyncWeb3", return_value=mock_web3):
            with patch("forge.virtuals.chains.evm_client.AsyncHTTPProvider"):
                await evm_client.initialize()

                balance = await evm_client.get_virtual_balance("0x" + "1" * 40)

                assert balance == 100.0

    @pytest.mark.asyncio
    async def test_get_virtual_balance_no_address_configured(self, evm_client, mock_web3):
        """Test getting VIRTUAL balance when address not configured."""
        evm_client.config.get_contract_address = MagicMock(return_value=None)

        with patch("forge.virtuals.chains.evm_client.AsyncWeb3", return_value=mock_web3):
            with patch("forge.virtuals.chains.evm_client.AsyncHTTPProvider"):
                await evm_client.initialize()

                with pytest.raises(ChainClientError, match="not configured"):
                    await evm_client.get_virtual_balance("0x" + "1" * 40)

    @pytest.mark.asyncio
    async def test_create_wallet(self, evm_client, mock_web3):
        """Test creating a new wallet."""
        with patch("forge.virtuals.chains.evm_client.AsyncWeb3", return_value=mock_web3):
            with patch("forge.virtuals.chains.evm_client.AsyncHTTPProvider"):
                with patch("forge.virtuals.chains.evm_client.Account") as MockAccount:
                    mock_account = MagicMock()
                    mock_account.address = "0x" + "a" * 40
                    mock_account.key.hex = MagicMock(return_value="0x" + "b" * 64)
                    MockAccount.create = MagicMock(return_value=mock_account)

                    await evm_client.initialize()

                    wallet_info, private_key = await evm_client.create_wallet()

                    assert wallet_info.address == "0x" + "a" * 40
                    assert wallet_info.chain == "base"
                    assert private_key == "0x" + "b" * 64


# ==================== Transaction Operations Tests ====================


class TestTransactionOperations:
    """Tests for transaction operations."""

    @pytest.mark.asyncio
    async def test_send_transaction_success(self, evm_client, mock_web3, mock_config):
        """Test sending a transaction successfully."""
        mock_config.operator_private_key = "0x" + "1" * 64

        mock_account = MagicMock()
        mock_account.address = "0x" + "a" * 40
        mock_account.sign_transaction = MagicMock(
            return_value=MagicMock(raw_transaction=b"\x00" * 100)
        )

        with patch("forge.virtuals.chains.evm_client.AsyncWeb3", return_value=mock_web3):
            with patch("forge.virtuals.chains.evm_client.AsyncHTTPProvider"):
                with patch("forge.virtuals.chains.evm_client.Account") as MockAccount:
                    MockAccount.from_key = MagicMock(return_value=mock_account)

                    await evm_client.initialize()

                    tx_record = await evm_client.send_transaction(
                        to_address="0x" + "2" * 40,
                        value=0.1,
                    )

                    assert tx_record.status == "pending"

    @pytest.mark.asyncio
    async def test_send_transaction_no_operator(self, evm_client, mock_web3):
        """Test sending transaction without operator account."""
        with patch("forge.virtuals.chains.evm_client.AsyncWeb3", return_value=mock_web3):
            with patch("forge.virtuals.chains.evm_client.AsyncHTTPProvider"):
                await evm_client.initialize()

                with pytest.raises(ChainClientError, match="No operator account"):
                    await evm_client.send_transaction(to_address="0x" + "2" * 40)

    @pytest.mark.asyncio
    async def test_send_transaction_negative_value(self, evm_client, mock_web3, mock_config):
        """Test sending transaction with negative value."""
        mock_config.operator_private_key = "0x" + "1" * 64

        mock_account = MagicMock()
        mock_account.address = "0x" + "a" * 40

        with patch("forge.virtuals.chains.evm_client.AsyncWeb3", return_value=mock_web3):
            with patch("forge.virtuals.chains.evm_client.AsyncHTTPProvider"):
                with patch("forge.virtuals.chains.evm_client.Account") as MockAccount:
                    MockAccount.from_key = MagicMock(return_value=mock_account)

                    await evm_client.initialize()

                    with pytest.raises(ValueError, match="cannot be negative"):
                        await evm_client.send_transaction(
                            to_address="0x" + "2" * 40,
                            value=-1.0,
                        )

    @pytest.mark.asyncio
    async def test_estimate_gas(self, evm_client, mock_web3):
        """Test gas estimation."""
        with patch("forge.virtuals.chains.evm_client.AsyncWeb3", return_value=mock_web3):
            with patch("forge.virtuals.chains.evm_client.AsyncHTTPProvider"):
                await evm_client.initialize()

                gas = await evm_client.estimate_gas(
                    to_address="0x" + "2" * 40,
                    value=0.1,
                )

                assert gas == 21000

    @pytest.mark.asyncio
    async def test_get_current_block(self, evm_client, mock_web3):
        """Test getting current block number."""
        with patch("forge.virtuals.chains.evm_client.AsyncWeb3", return_value=mock_web3):
            with patch("forge.virtuals.chains.evm_client.AsyncHTTPProvider"):
                await evm_client.initialize()

                block = await evm_client.get_current_block()

                assert block == 12345


# ==================== Token Operations Tests ====================


class TestTokenOperations:
    """Tests for token operations."""

    @pytest.mark.asyncio
    async def test_transfer_tokens(self, evm_client, mock_web3, mock_config):
        """Test token transfer."""
        mock_config.operator_private_key = "0x" + "1" * 64

        mock_account = MagicMock()
        mock_account.address = "0x" + "a" * 40
        mock_account.sign_transaction = MagicMock(
            return_value=MagicMock(raw_transaction=b"\x00" * 100)
        )

        mock_contract = MagicMock()
        mock_contract.functions.decimals = MagicMock(
            return_value=MagicMock(call=AsyncMock(return_value=18))
        )
        mock_contract.encodeABI = MagicMock(return_value="0x" + "f" * 64)
        mock_web3.eth.contract = MagicMock(return_value=mock_contract)

        with patch("forge.virtuals.chains.evm_client.AsyncWeb3", return_value=mock_web3):
            with patch("forge.virtuals.chains.evm_client.AsyncHTTPProvider"):
                with patch("forge.virtuals.chains.evm_client.Account") as MockAccount:
                    MockAccount.from_key = MagicMock(return_value=mock_account)

                    await evm_client.initialize()

                    tx_record = await evm_client.transfer_tokens(
                        token_address="0x" + "1" * 40,
                        to_address="0x" + "2" * 40,
                        amount=100.0,
                    )

                    assert tx_record.transaction_type == "token_transfer"

    @pytest.mark.asyncio
    async def test_approve_tokens_unlimited_requires_flag(self, evm_client, mock_web3, mock_config):
        """Test that unlimited approval requires explicit flag."""
        mock_config.operator_private_key = "0x" + "1" * 64

        mock_account = MagicMock()
        mock_account.address = "0x" + "a" * 40

        with patch("forge.virtuals.chains.evm_client.AsyncWeb3", return_value=mock_web3):
            with patch("forge.virtuals.chains.evm_client.AsyncHTTPProvider"):
                with patch("forge.virtuals.chains.evm_client.Account") as MockAccount:
                    MockAccount.from_key = MagicMock(return_value=mock_account)

                    await evm_client.initialize()

                    with pytest.raises(ValueError, match="allow_unlimited=True"):
                        await evm_client.approve_tokens(
                            token_address="0x" + "1" * 40,
                            spender_address="0x" + "2" * 40,
                            amount=float("inf"),
                        )


# ==================== Validation Tests ====================


class TestValidation:
    """Tests for input validation."""

    def test_validate_address_valid(self, evm_client, mock_web3):
        """Test validating a valid Ethereum address."""
        evm_client._w3 = mock_web3

        valid_address = "0x" + "a" * 40
        result = evm_client._validate_address(valid_address)
        assert result == valid_address

    def test_validate_address_invalid_format(self, evm_client, mock_web3):
        """Test validating an invalid address format."""
        evm_client._w3 = mock_web3

        with pytest.raises(ValueError, match="Invalid Ethereum address"):
            evm_client._validate_address("not_an_address")

    def test_validate_address_wrong_length(self, evm_client, mock_web3):
        """Test validating address with wrong length."""
        evm_client._w3 = mock_web3

        with pytest.raises(ValueError, match="Invalid Ethereum address"):
            evm_client._validate_address("0x" + "a" * 39)  # Too short

    def test_validate_bytes32_hex_string(self):
        """Test validating bytes32 from hex string."""
        hex_str = "0x" + "a" * 64
        result = EVMChainClient._validate_bytes32(hex_str)
        assert len(result) == 32

    def test_validate_bytes32_bytes(self):
        """Test validating bytes32 from bytes."""
        data = b"\x00" * 32
        result = EVMChainClient._validate_bytes32(data)
        assert result == data

    def test_validate_bytes32_wrong_length(self):
        """Test validating bytes32 with wrong length."""
        with pytest.raises(ValueError, match="exactly 32 bytes"):
            EVMChainClient._validate_bytes32(b"\x00" * 16)

    def test_validate_amount_positive(self):
        """Test validating positive amount."""
        EVMChainClient._validate_amount(100.0)  # Should not raise

    def test_validate_amount_zero(self):
        """Test validating zero amount."""
        with pytest.raises(ValueError, match="greater than zero"):
            EVMChainClient._validate_amount(0)

    def test_validate_amount_negative(self):
        """Test validating negative amount."""
        with pytest.raises(ValueError, match="greater than zero"):
            EVMChainClient._validate_amount(-10.0)

    def test_validate_amount_exceeds_max(self):
        """Test validating amount exceeding max."""
        with pytest.raises(ValueError, match="exceeds maximum"):
            EVMChainClient._validate_amount(1000.0, max_amount=100.0)


# ==================== Contract Operations Tests ====================


class TestContractOperations:
    """Tests for contract operations."""

    @pytest.mark.asyncio
    async def test_call_contract_requires_abi(self, evm_client, mock_web3):
        """Test that call_contract requires ABI."""
        with patch("forge.virtuals.chains.evm_client.AsyncWeb3", return_value=mock_web3):
            with patch("forge.virtuals.chains.evm_client.AsyncHTTPProvider"):
                await evm_client.initialize()

                with pytest.raises(ChainClientError, match="ABI required"):
                    await evm_client.call_contract(
                        contract_address="0x" + "1" * 40,
                        function_name="balanceOf",
                        args=["0x" + "2" * 40],
                    )

    @pytest.mark.asyncio
    async def test_execute_contract_requires_abi(self, evm_client, mock_web3):
        """Test that execute_contract requires ABI."""
        with patch("forge.virtuals.chains.evm_client.AsyncWeb3", return_value=mock_web3):
            with patch("forge.virtuals.chains.evm_client.AsyncHTTPProvider"):
                await evm_client.initialize()

                with pytest.raises(ChainClientError, match="ABI required"):
                    await evm_client.execute_contract(
                        contract_address="0x" + "1" * 40,
                        function_name="transfer",
                        args=["0x" + "2" * 40, 100],
                    )


# ==================== ERC20 ABI Tests ====================


class TestERC20ABI:
    """Tests for the ERC20 ABI."""

    def test_abi_contains_balance_of(self):
        """Test that ABI contains balanceOf."""
        balance_of = next((f for f in ERC20_ABI if f.get("name") == "balanceOf"), None)
        assert balance_of is not None
        assert balance_of["constant"] is True

    def test_abi_contains_transfer(self):
        """Test that ABI contains transfer."""
        transfer = next((f for f in ERC20_ABI if f.get("name") == "transfer"), None)
        assert transfer is not None

    def test_abi_contains_approve(self):
        """Test that ABI contains approve."""
        approve = next((f for f in ERC20_ABI if f.get("name") == "approve"), None)
        assert approve is not None

    def test_abi_contains_decimals(self):
        """Test that ABI contains decimals."""
        decimals = next((f for f in ERC20_ABI if f.get("name") == "decimals"), None)
        assert decimals is not None
