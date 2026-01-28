"""
Tests for the Multi-Chain Client Base module.

This module tests the abstract base class for blockchain interactions
and the MultiChainManager for coordinating across chains.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from forge.virtuals.chains.base_client import (
    BaseChainClient,
    ChainClientError,
    ContractNotFoundError,
    InsufficientFundsError,
    MultiChainManager,
    TransactionFailedError,
    get_chain_manager,
)
from forge.virtuals.config import ChainNetwork


# ==================== Fixtures ====================


@pytest.fixture
def mock_config():
    """Create a mock VirtualsConfig."""
    config = MagicMock()
    config.enabled_chains = [ChainNetwork.BASE, ChainNetwork.ETHEREUM]
    config.primary_chain = ChainNetwork.BASE
    config.get_rpc_endpoint = MagicMock(return_value="https://rpc.example.com")
    config.get_contract_address = MagicMock(return_value="0x" + "1" * 40)
    return config


@pytest.fixture
def mock_evm_client():
    """Create a mock EVM client."""
    client = MagicMock(spec=BaseChainClient)
    client.chain = ChainNetwork.BASE
    client.initialize = AsyncMock()
    client.close = AsyncMock()
    client.get_virtual_balance = AsyncMock(return_value=100.0)
    client._initialized = True
    return client


@pytest.fixture
def mock_solana_client():
    """Create a mock Solana client."""
    client = MagicMock(spec=BaseChainClient)
    client.chain = ChainNetwork.SOLANA
    client.initialize = AsyncMock()
    client.close = AsyncMock()
    client.get_virtual_balance = AsyncMock(return_value=50.0)
    client._initialized = True
    return client


@pytest.fixture(autouse=True)
async def reset_global_manager():
    """Reset global chain manager before and after each test."""
    import forge.virtuals.chains.base_client as base_module
    original = base_module._chain_manager
    base_module._chain_manager = None
    yield
    base_module._chain_manager = original


# ==================== Exception Tests ====================


class TestExceptions:
    """Tests for chain client exceptions."""

    def test_chain_client_error(self):
        """Test ChainClientError base exception."""
        error = ChainClientError("Test error")
        assert isinstance(error, Exception)
        assert str(error) == "Test error"

    def test_insufficient_funds_error(self):
        """Test InsufficientFundsError exception."""
        error = InsufficientFundsError("Not enough ETH")
        assert isinstance(error, ChainClientError)
        assert isinstance(error, Exception)

    def test_transaction_failed_error(self):
        """Test TransactionFailedError exception."""
        error = TransactionFailedError("Transaction reverted")
        assert isinstance(error, ChainClientError)

    def test_contract_not_found_error(self):
        """Test ContractNotFoundError exception."""
        error = ContractNotFoundError("Contract not deployed")
        assert isinstance(error, ChainClientError)


# ==================== BaseChainClient Tests ====================


class TestBaseChainClient:
    """Tests for BaseChainClient abstract base class."""

    def test_base_chain_client_is_abstract(self):
        """Test that BaseChainClient cannot be instantiated directly."""
        with pytest.raises(TypeError, match="abstract"):
            BaseChainClient(ChainNetwork.BASE)  # type: ignore

    def test_concrete_implementation(self, mock_config):
        """Test a concrete implementation of BaseChainClient."""
        # Create a minimal concrete implementation
        class TestChainClient(BaseChainClient):
            async def initialize(self):
                self._initialized = True

            async def close(self):
                self._initialized = False

            async def get_wallet_balance(self, address, token_address=None):
                return 100.0

            async def get_virtual_balance(self, address):
                return 50.0

            async def create_wallet(self):
                from forge.virtuals.models import WalletInfo
                return WalletInfo(address="0x123", chain="base"), "private_key"

            async def send_transaction(self, to_address, value=0, data=None, gas_limit=None):
                pass

            async def wait_for_transaction(self, tx_hash, timeout_seconds=120):
                pass

            async def get_transaction(self, tx_hash):
                return None

            async def estimate_gas(self, to_address, value=0, data=None):
                return 21000

            async def transfer_tokens(self, token_address, to_address, amount):
                pass

            async def approve_tokens(self, token_address, spender_address, amount):
                pass

            async def get_token_info(self, token_address):
                pass

            async def call_contract(self, contract_address, function_name, args, abi=None):
                pass

            async def execute_contract(self, contract_address, function_name, args, value=0, abi=None):
                pass

            async def get_current_block(self):
                return 12345

            async def get_block_timestamp(self, block_number):
                from datetime import UTC, datetime
                return datetime.now(UTC)

        with patch("forge.virtuals.chains.base_client.get_virtuals_config", return_value=mock_config):
            client = TestChainClient(ChainNetwork.BASE)
            assert client.chain == ChainNetwork.BASE
            assert client._initialized is False

    def test_ensure_initialized_raises(self, mock_config):
        """Test that _ensure_initialized raises when not initialized."""
        class TestClient(BaseChainClient):
            async def initialize(self):
                pass
            async def close(self):
                pass
            async def get_wallet_balance(self, address, token_address=None):
                return 0.0
            async def get_virtual_balance(self, address):
                return 0.0
            async def create_wallet(self):
                return MagicMock(), "key"
            async def send_transaction(self, to_address, value=0, data=None, gas_limit=None):
                pass
            async def wait_for_transaction(self, tx_hash, timeout_seconds=120):
                pass
            async def get_transaction(self, tx_hash):
                return None
            async def estimate_gas(self, to_address, value=0, data=None):
                return 21000
            async def transfer_tokens(self, token_address, to_address, amount):
                pass
            async def approve_tokens(self, token_address, spender_address, amount):
                pass
            async def get_token_info(self, token_address):
                pass
            async def call_contract(self, contract_address, function_name, args, abi=None):
                pass
            async def execute_contract(self, contract_address, function_name, args, value=0, abi=None):
                pass
            async def get_current_block(self):
                return 0
            async def get_block_timestamp(self, block_number):
                from datetime import UTC, datetime
                return datetime.now(UTC)

        with patch("forge.virtuals.chains.base_client.get_virtuals_config", return_value=mock_config):
            client = TestClient(ChainNetwork.BASE)

            with pytest.raises(ChainClientError, match="not initialized"):
                client._ensure_initialized()

    def test_is_initialized_property(self, mock_config):
        """Test the is_initialized property."""
        class TestClient(BaseChainClient):
            async def initialize(self):
                self._initialized = True
            async def close(self):
                pass
            async def get_wallet_balance(self, address, token_address=None):
                return 0.0
            async def get_virtual_balance(self, address):
                return 0.0
            async def create_wallet(self):
                return MagicMock(), "key"
            async def send_transaction(self, to_address, value=0, data=None, gas_limit=None):
                pass
            async def wait_for_transaction(self, tx_hash, timeout_seconds=120):
                pass
            async def get_transaction(self, tx_hash):
                return None
            async def estimate_gas(self, to_address, value=0, data=None):
                return 21000
            async def transfer_tokens(self, token_address, to_address, amount):
                pass
            async def approve_tokens(self, token_address, spender_address, amount):
                pass
            async def get_token_info(self, token_address):
                pass
            async def call_contract(self, contract_address, function_name, args, abi=None):
                pass
            async def execute_contract(self, contract_address, function_name, args, value=0, abi=None):
                pass
            async def get_current_block(self):
                return 0
            async def get_block_timestamp(self, block_number):
                from datetime import UTC, datetime
                return datetime.now(UTC)

        with patch("forge.virtuals.chains.base_client.get_virtuals_config", return_value=mock_config):
            client = TestClient(ChainNetwork.BASE)

            assert client.is_initialized is False

    def test_get_contract_address(self, mock_config):
        """Test get_contract_address utility method."""
        class TestClient(BaseChainClient):
            async def initialize(self):
                pass
            async def close(self):
                pass
            async def get_wallet_balance(self, address, token_address=None):
                return 0.0
            async def get_virtual_balance(self, address):
                return 0.0
            async def create_wallet(self):
                return MagicMock(), "key"
            async def send_transaction(self, to_address, value=0, data=None, gas_limit=None):
                pass
            async def wait_for_transaction(self, tx_hash, timeout_seconds=120):
                pass
            async def get_transaction(self, tx_hash):
                return None
            async def estimate_gas(self, to_address, value=0, data=None):
                return 21000
            async def transfer_tokens(self, token_address, to_address, amount):
                pass
            async def approve_tokens(self, token_address, spender_address, amount):
                pass
            async def get_token_info(self, token_address):
                pass
            async def call_contract(self, contract_address, function_name, args, abi=None):
                pass
            async def execute_contract(self, contract_address, function_name, args, value=0, abi=None):
                pass
            async def get_current_block(self):
                return 0
            async def get_block_timestamp(self, block_number):
                from datetime import UTC, datetime
                return datetime.now(UTC)

        with patch("forge.virtuals.chains.base_client.get_virtuals_config", return_value=mock_config):
            client = TestClient(ChainNetwork.BASE)

            address = client.get_contract_address("virtual_token")
            assert address == "0x" + "1" * 40
            mock_config.get_contract_address.assert_called_with(ChainNetwork.BASE, "virtual_token")

    def test_virtual_token_address_property(self, mock_config):
        """Test the virtual_token_address property."""
        class TestClient(BaseChainClient):
            async def initialize(self):
                pass
            async def close(self):
                pass
            async def get_wallet_balance(self, address, token_address=None):
                return 0.0
            async def get_virtual_balance(self, address):
                return 0.0
            async def create_wallet(self):
                return MagicMock(), "key"
            async def send_transaction(self, to_address, value=0, data=None, gas_limit=None):
                pass
            async def wait_for_transaction(self, tx_hash, timeout_seconds=120):
                pass
            async def get_transaction(self, tx_hash):
                return None
            async def estimate_gas(self, to_address, value=0, data=None):
                return 21000
            async def transfer_tokens(self, token_address, to_address, amount):
                pass
            async def approve_tokens(self, token_address, spender_address, amount):
                pass
            async def get_token_info(self, token_address):
                pass
            async def call_contract(self, contract_address, function_name, args, abi=None):
                pass
            async def execute_contract(self, contract_address, function_name, args, value=0, abi=None):
                pass
            async def get_current_block(self):
                return 0
            async def get_block_timestamp(self, block_number):
                from datetime import UTC, datetime
                return datetime.now(UTC)

        with patch("forge.virtuals.chains.base_client.get_virtuals_config", return_value=mock_config):
            client = TestClient(ChainNetwork.BASE)

            address = client.virtual_token_address
            assert address is not None


# ==================== MultiChainManager Tests ====================


class TestMultiChainManager:
    """Tests for MultiChainManager."""

    @pytest.mark.asyncio
    async def test_initialize(self, mock_config):
        """Test manager initialization."""
        with patch("forge.virtuals.chains.base_client.get_virtuals_config", return_value=mock_config):
            with patch("forge.virtuals.chains.base_client.EVMChainClient") as MockEVMClient:
                mock_client = MagicMock()
                mock_client.initialize = AsyncMock()
                MockEVMClient.return_value = mock_client

                manager = MultiChainManager()
                await manager.initialize()

                assert manager._initialized is True
                assert len(manager._clients) == 2  # BASE and ETHEREUM

    @pytest.mark.asyncio
    async def test_initialize_with_solana(self, mock_config):
        """Test manager initialization with Solana."""
        mock_config.enabled_chains = [ChainNetwork.BASE, ChainNetwork.SOLANA]

        with patch("forge.virtuals.chains.base_client.get_virtuals_config", return_value=mock_config):
            with patch("forge.virtuals.chains.base_client.EVMChainClient") as MockEVMClient:
                with patch("forge.virtuals.chains.base_client.SolanaChainClient") as MockSolanaClient:
                    mock_evm = MagicMock()
                    mock_evm.initialize = AsyncMock()
                    MockEVMClient.return_value = mock_evm

                    mock_solana = MagicMock()
                    mock_solana.initialize = AsyncMock()
                    MockSolanaClient.return_value = mock_solana

                    manager = MultiChainManager()
                    await manager.initialize()

                    assert ChainNetwork.BASE in manager._clients
                    assert ChainNetwork.SOLANA in manager._clients

    @pytest.mark.asyncio
    async def test_close(self, mock_config, mock_evm_client):
        """Test closing the manager."""
        with patch("forge.virtuals.chains.base_client.get_virtuals_config", return_value=mock_config):
            manager = MultiChainManager()
            manager._clients = {ChainNetwork.BASE: mock_evm_client}
            manager._initialized = True

            await manager.close()

            mock_evm_client.close.assert_called_once()
            assert manager._initialized is False
            assert len(manager._clients) == 0

    def test_get_client_success(self, mock_config, mock_evm_client):
        """Test getting a client successfully."""
        with patch("forge.virtuals.chains.base_client.get_virtuals_config", return_value=mock_config):
            manager = MultiChainManager()
            manager._clients = {ChainNetwork.BASE: mock_evm_client}

            client = manager.get_client(ChainNetwork.BASE)

            assert client is mock_evm_client

    def test_get_client_not_enabled(self, mock_config):
        """Test getting a client for non-enabled chain."""
        with patch("forge.virtuals.chains.base_client.get_virtuals_config", return_value=mock_config):
            manager = MultiChainManager()
            manager._clients = {}

            with pytest.raises(ChainClientError, match="not enabled or initialized"):
                manager.get_client(ChainNetwork.SOLANA)

    def test_primary_client_property(self, mock_config, mock_evm_client):
        """Test the primary_client property."""
        with patch("forge.virtuals.chains.base_client.get_virtuals_config", return_value=mock_config):
            manager = MultiChainManager()
            manager._clients = {ChainNetwork.BASE: mock_evm_client}

            client = manager.primary_client

            assert client is mock_evm_client

    @pytest.mark.asyncio
    async def test_get_total_virtual_balance(self, mock_config, mock_evm_client):
        """Test getting total VIRTUAL balance across chains."""
        mock_evm_client.get_virtual_balance = AsyncMock(return_value=100.0)

        with patch("forge.virtuals.chains.base_client.get_virtuals_config", return_value=mock_config):
            manager = MultiChainManager()
            manager._clients = {ChainNetwork.BASE: mock_evm_client}

            addresses = {"base": "0x123"}
            total = await manager.get_total_virtual_balance(addresses)

            assert total == 100.0

    @pytest.mark.asyncio
    async def test_get_total_virtual_balance_multiple_chains(self, mock_config, mock_evm_client, mock_solana_client):
        """Test getting total balance from multiple chains."""
        mock_evm_client.get_virtual_balance = AsyncMock(return_value=100.0)
        mock_solana_client.get_virtual_balance = AsyncMock(return_value=50.0)

        mock_config.enabled_chains = [ChainNetwork.BASE, ChainNetwork.SOLANA]

        with patch("forge.virtuals.chains.base_client.get_virtuals_config", return_value=mock_config):
            manager = MultiChainManager()
            manager._clients = {
                ChainNetwork.BASE: mock_evm_client,
                ChainNetwork.SOLANA: mock_solana_client,
            }

            addresses = {"base": "0x123", "solana": "7B8xLj..."}
            total = await manager.get_total_virtual_balance(addresses)

            assert total == 150.0

    @pytest.mark.asyncio
    async def test_get_total_virtual_balance_with_error(self, mock_config, mock_evm_client):
        """Test that balance errors are handled gracefully."""
        mock_evm_client.get_virtual_balance = AsyncMock(
            side_effect=ConnectionError("Network error")
        )

        with patch("forge.virtuals.chains.base_client.get_virtuals_config", return_value=mock_config):
            manager = MultiChainManager()
            manager._clients = {ChainNetwork.BASE: mock_evm_client}

            addresses = {"base": "0x123"}
            total = await manager.get_total_virtual_balance(addresses)

            # Should return 0 and not raise
            assert total == 0.0


# ==================== Global Manager Tests ====================


class TestGlobalManager:
    """Tests for the global chain manager."""

    @pytest.mark.asyncio
    async def test_get_chain_manager_creates_singleton(self, mock_config):
        """Test that get_chain_manager returns a singleton."""
        with patch("forge.virtuals.chains.base_client.get_virtuals_config", return_value=mock_config):
            with patch("forge.virtuals.chains.base_client.EVMChainClient") as MockEVMClient:
                mock_client = MagicMock()
                mock_client.initialize = AsyncMock()
                MockEVMClient.return_value = mock_client

                manager1 = await get_chain_manager()
                manager2 = await get_chain_manager()

                assert manager1 is manager2

    @pytest.mark.asyncio
    async def test_get_chain_manager_initializes(self, mock_config):
        """Test that get_chain_manager initializes the manager."""
        with patch("forge.virtuals.chains.base_client.get_virtuals_config", return_value=mock_config):
            with patch("forge.virtuals.chains.base_client.EVMChainClient") as MockEVMClient:
                mock_client = MagicMock()
                mock_client.initialize = AsyncMock()
                MockEVMClient.return_value = mock_client

                manager = await get_chain_manager()

                assert manager._initialized is True


# ==================== Integration Tests ====================


class TestChainClientIntegration:
    """Integration tests for chain client behavior."""

    @pytest.mark.asyncio
    async def test_full_manager_lifecycle(self, mock_config):
        """Test complete lifecycle of manager."""
        with patch("forge.virtuals.chains.base_client.get_virtuals_config", return_value=mock_config):
            with patch("forge.virtuals.chains.base_client.EVMChainClient") as MockEVMClient:
                mock_client = MagicMock()
                mock_client.initialize = AsyncMock()
                mock_client.close = AsyncMock()
                MockEVMClient.return_value = mock_client

                manager = MultiChainManager()

                # Initialize
                await manager.initialize()
                assert manager._initialized is True

                # Get client
                client = manager.get_client(ChainNetwork.BASE)
                assert client is mock_client

                # Close
                await manager.close()
                assert manager._initialized is False
                mock_client.close.assert_called()
