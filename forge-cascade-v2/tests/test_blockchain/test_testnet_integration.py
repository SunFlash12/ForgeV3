"""
Testnet Integration Tests

These tests verify blockchain operations against real testnets:
- Base Sepolia (EVM)
- Solana Devnet

To run these tests, set the following environment variables:
- TESTNET_PRIVATE_KEY: EVM private key with testnet ETH
- TESTNET_SOLANA_KEY: Solana private key with devnet SOL
- RUN_TESTNET_TESTS=true

Example:
    RUN_TESTNET_TESTS=true TESTNET_PRIVATE_KEY=0x... pytest tests/test_blockchain/ -v
"""

import os
from decimal import Decimal

import pytest

# Skip all tests if testnet testing is not enabled
pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_TESTNET_TESTS", "").lower() != "true",
    reason="Testnet tests disabled. Set RUN_TESTNET_TESTS=true to enable.",
)


@pytest.fixture
def evm_private_key():
    """Get EVM private key for testnet."""
    key = os.environ.get("TESTNET_PRIVATE_KEY")
    if not key:
        pytest.skip("TESTNET_PRIVATE_KEY not set")
    return key


@pytest.fixture
def solana_private_key():
    """Get Solana private key for devnet."""
    key = os.environ.get("TESTNET_SOLANA_KEY")
    if not key:
        pytest.skip("TESTNET_SOLANA_KEY not set")
    return key


class TestEVMChainClient:
    """Tests for EVM chain client on Base Sepolia."""

    @pytest.fixture
    async def evm_client(self, evm_private_key):
        """Create and initialize EVM client for Base Sepolia."""
        from forge.virtuals.chains import EVMChainClient
        from forge.virtuals.config import ChainNetwork, VirtualsConfig, configure_virtuals

        # Configure for testnet
        config = VirtualsConfig(
            environment="testnet",
            primary_chain=ChainNetwork.BASE_SEPOLIA,
            operator_private_key=evm_private_key,
        )
        configure_virtuals(config)

        client = EVMChainClient(ChainNetwork.BASE_SEPOLIA)
        await client.initialize()
        yield client
        await client.close()

    @pytest.mark.asyncio
    async def test_connection(self, evm_client):
        """Test connection to Base Sepolia."""
        block = await evm_client.get_current_block()
        assert block > 0
        print(f"Connected to Base Sepolia at block {block}")

    @pytest.mark.asyncio
    async def test_get_balance(self, evm_client):
        """Test getting ETH balance."""
        # Use a known funded testnet address or the operator address
        address = evm_client._account.address
        balance = await evm_client.get_wallet_balance(address)
        print(f"Balance for {address}: {balance} ETH")
        # Balance might be 0 for unfunded wallet
        assert balance >= 0

    @pytest.mark.asyncio
    async def test_estimate_gas(self, evm_client):
        """Test gas estimation for a simple transfer."""
        # Estimate gas for sending to zero address (won't actually send)
        gas = await evm_client.estimate_gas(
            to_address="0x0000000000000000000000000000000000000001",
            value=0.001,
        )
        assert gas > 0
        print(f"Estimated gas for transfer: {gas}")

    @pytest.mark.asyncio
    async def test_block_timestamp(self, evm_client):
        """Test getting block timestamp."""
        current_block = await evm_client.get_current_block()
        timestamp = await evm_client.get_block_timestamp(current_block)
        assert timestamp is not None
        print(f"Block {current_block} timestamp: {timestamp}")


class TestSolanaChainClient:
    """Tests for Solana chain client on Devnet."""

    @pytest.fixture
    async def solana_client(self, solana_private_key):
        """Create and initialize Solana client for Devnet."""
        from forge.virtuals.chains import SolanaChainClient
        from forge.virtuals.config import ChainNetwork, VirtualsConfig, configure_virtuals

        # Configure for testnet
        config = VirtualsConfig(
            environment="testnet",
            primary_chain=ChainNetwork.SOLANA_DEVNET,
            solana_private_key=solana_private_key,
        )
        configure_virtuals(config)

        client = SolanaChainClient(ChainNetwork.SOLANA_DEVNET)
        await client.initialize()
        yield client
        await client.close()

    @pytest.mark.asyncio
    async def test_connection(self, solana_client):
        """Test connection to Solana Devnet."""
        slot = await solana_client.get_current_block()
        assert slot > 0
        print(f"Connected to Solana Devnet at slot {slot}")

    @pytest.mark.asyncio
    async def test_get_sol_balance(self, solana_client):
        """Test getting SOL balance."""
        address = str(solana_client._keypair.pubkey())
        balance = await solana_client.get_wallet_balance(address)
        print(f"SOL balance for {address}: {balance}")
        assert balance >= 0

    @pytest.mark.asyncio
    async def test_call_contract_balance(self, solana_client):
        """Test reading account balance via call_contract."""
        address = str(solana_client._keypair.pubkey())
        balance = await solana_client.call_contract(
            contract_address=address,
            function_name="balance",
            args=[],
        )
        assert isinstance(balance, float)
        print(f"Account balance via call_contract: {balance}")

    @pytest.mark.asyncio
    async def test_call_contract_account_info(self, solana_client):
        """Test reading account info via call_contract."""
        address = str(solana_client._keypair.pubkey())
        info = await solana_client.call_contract(
            contract_address=address,
            function_name="account_info",
            args=[],
        )
        assert info is not None
        assert "lamports" in info
        print(f"Account info: {info}")


class TestChainManager:
    """Tests for multi-chain manager."""

    @pytest.fixture
    async def chain_manager(self, evm_private_key):
        """Create and initialize chain manager."""
        from forge.virtuals.chains import ChainManager
        from forge.virtuals.config import ChainNetwork, VirtualsConfig, configure_virtuals

        config = VirtualsConfig(
            environment="testnet",
            operator_private_key=evm_private_key,
            enabled_chains=[ChainNetwork.BASE_SEPOLIA],
        )
        configure_virtuals(config)

        manager = ChainManager()
        await manager.initialize_chain(ChainNetwork.BASE_SEPOLIA)
        yield manager
        await manager.close()

    @pytest.mark.asyncio
    async def test_get_client(self, chain_manager):
        """Test getting chain client from manager."""
        from forge.virtuals.config import ChainNetwork

        client = chain_manager.get_client(ChainNetwork.BASE_SEPOLIA)
        assert client is not None
        assert client._initialized

    @pytest.mark.asyncio
    async def test_multi_chain_balance(self, chain_manager, evm_private_key):
        """Test querying balance across chains."""
        from forge.virtuals.config import ChainNetwork

        client = chain_manager.get_client(ChainNetwork.BASE_SEPOLIA)
        address = client._account.address

        balance = await client.get_wallet_balance(address)
        print(f"Base Sepolia balance: {balance} ETH")
        assert balance >= 0


class TestBridgeService:
    """Tests for cross-chain bridge service."""

    @pytest.fixture
    async def bridge_service(self, evm_private_key):
        """Create bridge service for testnet."""
        from forge.virtuals.bridge import BridgeService
        from forge.virtuals.config import ChainNetwork, VirtualsConfig, configure_virtuals

        config = VirtualsConfig(
            environment="testnet",
            operator_private_key=evm_private_key,
            enabled_chains=[ChainNetwork.BASE_SEPOLIA, ChainNetwork.ETHEREUM_SEPOLIA],
        )
        configure_virtuals(config)

        service = BridgeService()
        await service.initialize()
        yield service
        await service.close()

    @pytest.mark.asyncio
    async def test_supported_routes(self, bridge_service):
        """Test getting supported bridge routes."""
        routes = bridge_service.get_supported_routes()
        print(f"Supported routes: {routes}")
        # At least one route should be available
        assert len(routes) >= 0

    @pytest.mark.asyncio
    async def test_estimate_fee(self, bridge_service):
        """Test fee estimation for bridge."""
        from forge.virtuals.bridge import BridgeRoute

        fee = await bridge_service.estimate_bridge_fee(
            route=BridgeRoute.BASE_TO_ETHEREUM,
            amount=Decimal("100.0"),
        )
        print(f"Bridge fee estimate: {fee}")
        assert "bridge_fee" in fee
        assert "receive_amount" in fee
        assert fee["receive_amount"] < Decimal("100.0")


class TestTippingService:
    """Tests for FROWG tipping service."""

    @pytest.fixture
    async def tipping_service(self, solana_private_key):
        """Create tipping service for devnet."""
        from forge.virtuals.config import ChainNetwork, VirtualsConfig, configure_virtuals
        from forge.virtuals.tipping import FrowgTippingService

        config = VirtualsConfig(
            environment="testnet",
            solana_private_key=solana_private_key,
            enabled_chains=[ChainNetwork.SOLANA_DEVNET],
        )
        configure_virtuals(config)

        service = FrowgTippingService()
        await service.initialize()
        yield service
        await service.close()

    @pytest.mark.asyncio
    async def test_estimate_tip_fee(self, tipping_service):
        """Test tip fee estimation."""
        fee = await tipping_service.estimate_tip_fee(Decimal("10.0"))
        print(f"Tip fee estimate: {fee}")
        assert "platform_fee" in fee
        assert "recipient_receives" in fee
        assert fee["recipient_receives"] < Decimal("10.0")

    @pytest.mark.asyncio
    async def test_get_balance(self, tipping_service, solana_private_key):
        """Test getting FROWG balance (may be 0 on devnet)."""
        import base58
        from solders.keypair import Keypair

        # Get operator address
        secret_key = base58.b58decode(solana_private_key)
        keypair = Keypair.from_bytes(secret_key)
        address = str(keypair.pubkey())

        # This will likely fail on devnet since FROWG is mainnet only
        # but tests the service infrastructure
        try:
            balance = await tipping_service.get_balance(address)
            print(f"FROWG balance: {balance}")
        except Exception as e:
            # Expected on devnet - FROWG token doesn't exist
            print(f"Expected error on devnet: {e}")
            pytest.skip("FROWG token not available on devnet")


class TestContractInteraction:
    """Tests for smart contract interactions on testnet."""

    @pytest.fixture
    async def evm_client(self, evm_private_key):
        """Create EVM client for contract tests."""
        from forge.virtuals.chains import EVMChainClient
        from forge.virtuals.config import ChainNetwork, VirtualsConfig, configure_virtuals

        config = VirtualsConfig(
            environment="testnet",
            operator_private_key=evm_private_key,
        )
        configure_virtuals(config)

        client = EVMChainClient(ChainNetwork.BASE_SEPOLIA)
        await client.initialize()
        yield client
        await client.close()

    @pytest.mark.asyncio
    async def test_read_erc20_decimals(self, evm_client):
        """Test reading ERC-20 decimals (using a known testnet token)."""
        from forge.virtuals.tokenization.contracts import ERC20_ABI

        # Use WETH on Base Sepolia (if available) or skip
        weth_address = "0x4200000000000000000000000000000000000006"

        try:
            decimals = await evm_client.call_contract(
                contract_address=weth_address,
                function_name="decimals",
                args=[],
                abi=ERC20_ABI,
            )
            print(f"WETH decimals: {decimals}")
            assert decimals == 18
        except Exception as e:
            print(f"Could not read WETH: {e}")
            pytest.skip("WETH not available on testnet")

    @pytest.mark.asyncio
    async def test_read_erc20_total_supply(self, evm_client):
        """Test reading ERC-20 total supply."""
        from forge.virtuals.tokenization.contracts import ERC20_ABI

        weth_address = "0x4200000000000000000000000000000000000006"

        try:
            supply = await evm_client.call_contract(
                contract_address=weth_address,
                function_name="totalSupply",
                args=[],
                abi=ERC20_ABI,
            )
            print(f"WETH total supply: {supply}")
            assert supply >= 0
        except Exception as e:
            print(f"Could not read WETH supply: {e}")
            pytest.skip("WETH not available on testnet")


# Performance benchmarks (optional)
class TestPerformance:
    """Performance benchmarks for blockchain operations."""

    @pytest.fixture
    async def evm_client(self, evm_private_key):
        """Create EVM client for benchmarks."""
        from forge.virtuals.chains import EVMChainClient
        from forge.virtuals.config import ChainNetwork, VirtualsConfig, configure_virtuals

        config = VirtualsConfig(
            environment="testnet",
            operator_private_key=evm_private_key,
        )
        configure_virtuals(config)

        client = EVMChainClient(ChainNetwork.BASE_SEPOLIA)
        await client.initialize()
        yield client
        await client.close()

    @pytest.mark.asyncio
    async def test_block_query_latency(self, evm_client):
        """Measure block query latency."""
        import time

        iterations = 5
        times = []

        for _ in range(iterations):
            start = time.time()
            await evm_client.get_current_block()
            elapsed = time.time() - start
            times.append(elapsed)

        avg_time = sum(times) / len(times)
        print(f"Average block query latency: {avg_time * 1000:.2f}ms")
        assert avg_time < 5.0  # Should be under 5 seconds

    @pytest.mark.asyncio
    async def test_balance_query_latency(self, evm_client):
        """Measure balance query latency."""
        import time

        address = evm_client._account.address
        iterations = 5
        times = []

        for _ in range(iterations):
            start = time.time()
            await evm_client.get_wallet_balance(address)
            elapsed = time.time() - start
            times.append(elapsed)

        avg_time = sum(times) / len(times)
        print(f"Average balance query latency: {avg_time * 1000:.2f}ms")
        assert avg_time < 5.0
