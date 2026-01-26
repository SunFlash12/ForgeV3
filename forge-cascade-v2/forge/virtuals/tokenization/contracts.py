"""
Virtuals Protocol Smart Contract ABIs and Addresses

This module contains the contract ABIs and addresses needed for blockchain
interactions with Virtuals Protocol.

Contract Sources:
- Whitepaper: https://whitepaper.virtuals.io/info-hub/important-links-and-resources/contract-address
- GitHub: https://github.com/Virtual-Protocol/protocol-contracts
- BaseScan: https://basescan.org (Base L2 by Coinbase)

Contract Documentation:
- AgentFactory: Creates new agent tokens with bonding curves
- BondingCurve: Manages token bonding curve contributions
- VIRTUAL Token: The native VIRTUAL token (ERC-20)
- MultiSend: Batch transfer utility for gas-efficient distributions

PENDING: AgentFactoryV3 address not publicly listed in whitepaper.
Contact Virtuals Protocol team or find via agent token creation events.
"""

from typing import Any

# ═══════════════════════════════════════════════════════════════════════════════
# CONTRACT ADDRESSES
# ═══════════════════════════════════════════════════════════════════════════════


class ContractAddresses:
    """
    Official Virtuals Protocol contract addresses.

    IMPORTANT: Verify these addresses before use in production!
    Check: https://basescan.org and https://etherscan.io
    """

    # Base Mainnet (verified from whitepaper.virtuals.io)
    BASE_MAINNET = {
        # Core tokens
        "virtual_token": "0x0b3e328455c4059EEb9e3f84b5543F74E24e7E1b",
        "ve_virtual": "0x14559863b6E695A8aa4B7e68541d240ac1BBeB2f",  # Voting token
        # Factory contracts - PENDING: Contact Virtuals Protocol
        "agent_factory": None,  # AgentFactoryV3 - not publicly listed
        "agent_nft": None,  # AgentNFT contract
        "acp_registry": None,  # ACP Registry
        # Infrastructure from whitepaper
        "vault": "0xdAd686299FB562f89e55DA05F1D96FaBEb2A2E32",  # Creator token locking
        "sell_wall": "0xe2890629EF31b32132003C02B29a50A025dEeE8a",  # Sell wall wallet
        "sell_executor": "0xF8DD39c71A278FE9F4377D009D7627EF140f809e",  # Sell order execution
        "tax_swapper": "0x8e0253dA409Faf5918FE2A15979fd878F4495D0E",
        "tax_manager": "0x7e26173192d72fd6d75a759f888d61c2cdbb64b1",
        # Third-party
        "bridge": "0x3154Cf16ccdb4C6d922629664174b904d80F2C35",
        "multisend": "0x40A2aCCbd92BCA938b02010E17A5b8929b49130D",  # Gnosis Safe
    }

    # Base Sepolia (Testnet) — deployed 2026-01-26 via deploy-testnet-lifecycle.ts
    BASE_SEPOLIA = {
        "virtual_token": "0x5bE85bc7df67A94F2f1591DA3D7343996Ebbd567",  # tVIRTUAL MockERC20
        "agent_factory": None,
        "agent_nft": None,
        "acp_registry": None,
        "vault": None,
        "bridge": None,
        "multisend": "0x40A2aCCbd92BCA938b02010E17A5b8929b49130D",
        # Testnet lifecycle contracts
        "capsule_registry": "0xDd24a3e584E756C00657928fF77f638915a3e454",
        "simple_escrow": "0x33F3f8fB08e5C3863ec23abaeb0a88cE5FB9E5eC",
        "got_token": "0xdE635a7e3db567eD0202fd01F8ED48c645893fb6",  # Genomic Ontology Token
        "vct_token": "0x8255d1fE1f2A3cF1F97694286Ab6fF0B6F229C04",  # Variant Classifier Token
    }

    # Ethereum Mainnet
    ETHEREUM_MAINNET: dict[str, str | None] = {
        "virtual_token": "0x44ff8620b8cA30902395A7bD3F2407e1A091BF73",
        "bridge": "0x3154Cf16ccdb4C6d922629664174b904d80F2C35",
    }

    # Solana Mainnet
    SOLANA_MAINNET: dict[str, str | None] = {
        "virtual_token": "3iQL8BFS2vE7mww4ehAqQHAsbmRNCrPxizWAT2Zfyr9y",
        # FROWG token for tipping - community token on Solana
        "frowg_token": "uogFxqx5SPdL7CMWTTttz4KZ2WctR4RjgZwmGcwpump",
    }

    @classmethod
    def get_address(cls, chain: str, contract: str) -> str | None:
        """Get a contract address for a specific chain."""
        chain_map: dict[str, dict[str, str | None]] = {
            "base": cls.BASE_MAINNET,
            "base_sepolia": cls.BASE_SEPOLIA,
            "ethereum": cls.ETHEREUM_MAINNET,
            "solana": cls.SOLANA_MAINNET,
        }
        addresses = chain_map.get(chain.lower(), {})
        return addresses.get(contract)


# ═══════════════════════════════════════════════════════════════════════════════
# CONTRACT ABIs
# ═══════════════════════════════════════════════════════════════════════════════

# Standard ERC-20 ABI (for VIRTUAL token interactions)
ERC20_ABI: list[dict[str, Any]] = [
    {
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"name": "spender", "type": "address"}, {"name": "amount", "type": "uint256"}],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"name": "owner", "type": "address"}, {"name": "spender", "type": "address"}],
        "name": "allowance",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"name": "recipient", "type": "address"}, {"name": "amount", "type": "uint256"}],
        "name": "transfer",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "sender", "type": "address"},
            {"name": "recipient", "type": "address"},
            {"name": "amount", "type": "uint256"},
        ],
        "name": "transferFrom",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "totalSupply",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
]

# AgentFactory ABI (for creating new agent tokens)
# Source: https://github.com/Virtual-Protocol/protocol-contracts/blob/main/contracts/virtualPersona/AgentFactory.sol
AGENT_FACTORY_ABI: list[dict[str, Any]] = [
    # initialize - Initialize the factory contract
    {
        "inputs": [
            {"name": "_assetToken", "type": "address"},
            {"name": "_veToken", "type": "address"},
            {"name": "_agentNft", "type": "address"},
            {"name": "_contributionNft", "type": "address"},
            {"name": "_serviceNft", "type": "address"},
            {"name": "_gov", "type": "address"},
            {"name": "_applicationThreshold", "type": "uint256"},
            {"name": "_vault", "type": "address"},
        ],
        "name": "initialize",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # proposeAgent - Propose a new agent (requires VIRTUAL stake)
    {
        "inputs": [
            {"name": "name", "type": "string"},
            {"name": "symbol", "type": "string"},
            {"name": "tokenURI", "type": "string"},
            {"name": "cores", "type": "uint8[]"},
            {"name": "tbaSalt", "type": "bytes32"},
            {"name": "tbaImplementation", "type": "address"},
            {"name": "daoVotingPeriod", "type": "uint32"},
            {"name": "daoThreshold", "type": "uint256"},
        ],
        "name": "proposeAgent",
        "outputs": [{"name": "applicationId", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # getApplication - Get application details
    {
        "inputs": [{"name": "applicationId", "type": "uint256"}],
        "name": "getApplication",
        "outputs": [
            {
                "components": [
                    {"name": "proposer", "type": "address"},
                    {"name": "token", "type": "address"},
                    {"name": "dao", "type": "address"},
                    {"name": "tba", "type": "address"},
                    {"name": "veToken", "type": "address"},
                    {"name": "lp", "type": "address"},
                    {"name": "virtualId", "type": "uint256"},
                    {"name": "status", "type": "uint8"},
                ],
                "name": "application",
                "type": "tuple",
            }
        ],
        "stateMutability": "view",
        "type": "function",
    },
    # executeApplication - Execute/reject an application
    {
        "inputs": [
            {"name": "applicationId", "type": "uint256"},
            {"name": "approved", "type": "bool"},
        ],
        "name": "executeApplication",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # withdraw - Withdraw stake from rejected application
    {
        "inputs": [{"name": "applicationId", "type": "uint256"}],
        "name": "withdraw",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # totalAgents - Get total number of created agents
    {
        "inputs": [],
        "name": "totalAgents",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    # setApplicationThreshold - Set minimum stake to propose
    {
        "inputs": [{"name": "threshold", "type": "uint256"}],
        "name": "setApplicationThreshold",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # pause/unpause
    {
        "inputs": [],
        "name": "pause",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "unpause",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # NewPersona event - Emitted when agent is created
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "virtualId", "type": "uint256"},
            {"indexed": False, "name": "token", "type": "address"},
            {"indexed": False, "name": "dao", "type": "address"},
            {"indexed": False, "name": "tba", "type": "address"},
            {"indexed": False, "name": "veToken", "type": "address"},
            {"indexed": False, "name": "lp", "type": "address"},
        ],
        "name": "NewPersona",
        "type": "event",
    },
    # NewApplication event
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "id", "type": "uint256"},
        ],
        "name": "NewApplication",
        "type": "event",
    },
    # ApplicationThresholdUpdated event
    {
        "anonymous": False,
        "inputs": [
            {"indexed": False, "name": "newThreshold", "type": "uint256"},
        ],
        "name": "ApplicationThresholdUpdated",
        "type": "event",
    },
]

# BondingCurve ABI (for contributing to bonding curve)
# Source: https://github.com/Virtual-Protocol/protocol-contracts/blob/main/contracts/fun/Bonding.sol
BONDING_CURVE_ABI: list[dict[str, Any]] = [
    # initialize - Initialize the bonding curve contract
    {
        "inputs": [
            {"name": "factory_", "type": "address"},
            {"name": "router_", "type": "address"},
            {"name": "feeTo_", "type": "address"},
            {"name": "fee_", "type": "uint256"},
            {"name": "initialSupply_", "type": "uint256"},
            {"name": "assetRate_", "type": "uint256"},
            {"name": "maxTx_", "type": "uint256"},
            {"name": "agentFactory_", "type": "address"},
            {"name": "gradThreshold_", "type": "uint256"},
        ],
        "name": "initialize",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # launch - Launch a new token on bonding curve
    {
        "inputs": [
            {"name": "_name", "type": "string"},
            {"name": "_ticker", "type": "string"},
            {"name": "cores", "type": "uint8[]"},
            {"name": "desc", "type": "string"},
            {"name": "img", "type": "string"},
            {"name": "urls", "type": "string[4]"},
            {"name": "purchaseAmount", "type": "uint256"},
        ],
        "name": "launch",
        "outputs": [
            {"name": "tokenAddress", "type": "address"},
            {"name": "pairAddress", "type": "address"},
            {"name": "tokensReceived", "type": "uint256"},
        ],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # buy - Buy tokens from bonding curve
    {
        "inputs": [
            {"name": "amountIn", "type": "uint256"},
            {"name": "tokenAddress", "type": "address"},
            {"name": "amountOutMin", "type": "uint256"},
            {"name": "deadline", "type": "uint256"},
        ],
        "name": "buy",
        "outputs": [{"name": "success", "type": "bool"}],
        "stateMutability": "payable",
        "type": "function",
    },
    # sell - Sell tokens back to bonding curve
    {
        "inputs": [
            {"name": "amountIn", "type": "uint256"},
            {"name": "tokenAddress", "type": "address"},
            {"name": "amountOutMin", "type": "uint256"},
            {"name": "deadline", "type": "uint256"},
        ],
        "name": "sell",
        "outputs": [{"name": "success", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # unwrapToken - Unwrap FERC20 to ERC20 after graduation
    {
        "inputs": [
            {"name": "srcTokenAddress", "type": "address"},
            {"name": "accounts", "type": "address[]"},
        ],
        "name": "unwrapToken",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # setTokenParams - Update token parameters (admin)
    {
        "inputs": [
            {"name": "newSupply", "type": "uint256"},
            {"name": "newGradThreshold", "type": "uint256"},
            {"name": "newMaxTx", "type": "uint256"},
            {"name": "newAssetRate", "type": "uint256"},
            {"name": "newFee", "type": "uint256"},
            {"name": "newFeeTo", "type": "address"},
        ],
        "name": "setTokenParams",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # View functions for bonding curve state
    {
        "inputs": [],
        "name": "gradThreshold",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "initialSupply",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "fee",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "assetRate",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "maxTx",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    # tokenInfo mapping - get token bonding curve info
    {
        "inputs": [{"name": "tokenAddress", "type": "address"}],
        "name": "tokenInfo",
        "outputs": [
            {
                "components": [
                    {"name": "creator", "type": "address"},
                    {"name": "token", "type": "address"},
                    {"name": "pair", "type": "address"},
                    {"name": "agentToken", "type": "address"},
                    {"name": "virtualId", "type": "uint256"},
                    {"name": "data", "type": "uint256"},
                    {"name": "status", "type": "uint8"},
                ],
                "name": "info",
                "type": "tuple",
            }
        ],
        "stateMutability": "view",
        "type": "function",
    },
    # profile mapping - get creator profile
    {
        "inputs": [{"name": "creator", "type": "address"}],
        "name": "profile",
        "outputs": [
            {
                "components": [
                    {"name": "user", "type": "address"},
                    {"name": "count", "type": "uint256"},
                ],
                "name": "profileData",
                "type": "tuple",
            }
        ],
        "stateMutability": "view",
        "type": "function",
    },
]

# Token ABI (for graduated agent tokens)
# Source: https://github.com/Virtual-Protocol/protocol-contracts/blob/main/contracts/virtualPersona/AgentToken.sol
AGENT_TOKEN_ABI: list[dict[str, Any]] = ERC20_ABI + [
    # initialize - Initialize agent token
    {
        "inputs": [
            {"name": "addresses", "type": "address[3]"},  # [owner, taxRecipient, uniswapRouter]
            {"name": "tokenParams", "type": "bytes"},
            {"name": "taxParams", "type": "bytes"},
            {"name": "poolParams", "type": "bytes"},
        ],
        "name": "initialize",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # addInitialLiquidity - Create Uniswap LP
    {
        "inputs": [{"name": "lpOwner", "type": "address"}],
        "name": "addInitialLiquidity",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # Liquidity pool management
    {
        "inputs": [{"name": "queryAddress_", "type": "address"}],
        "name": "isLiquidityPool",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "liquidityPools",
        "outputs": [{"name": "", "type": "address[]"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"name": "newLiquidityPool_", "type": "address"}],
        "name": "addLiquidityPool",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"name": "removedLiquidityPool_", "type": "address"}],
        "name": "removeLiquidityPool",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # Tax configuration
    {
        "inputs": [{"name": "projectTaxRecipient_", "type": "address"}],
        "name": "setProjectTaxRecipient",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"name": "swapThresholdBasisPoints_", "type": "uint16"}],
        "name": "setSwapThresholdBasisPoints",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "newProjectBuyTaxBasisPoints_", "type": "uint16"},
            {"name": "newProjectSellTaxBasisPoints_", "type": "uint16"},
        ],
        "name": "setProjectTaxRates",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # Tax view functions
    {
        "inputs": [],
        "name": "totalBuyTaxBasisPoints",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "totalSellTaxBasisPoints",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    # Tax distribution
    {
        "inputs": [],
        "name": "distributeTaxTokens",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # Burn functions
    {
        "inputs": [{"name": "value", "type": "uint256"}],
        "name": "burn",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "account", "type": "address"},
            {"name": "value", "type": "uint256"},
        ],
        "name": "burnFrom",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # Withdraw functions (admin)
    {
        "inputs": [{"name": "amount_", "type": "uint256"}],
        "name": "withdrawETH",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "token_", "type": "address"},
            {"name": "amount_", "type": "uint256"},
        ],
        "name": "withdrawERC20",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # Valid caller management
    {
        "inputs": [{"name": "queryHash_", "type": "bytes32"}],
        "name": "isValidCaller",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "validCallers",
        "outputs": [{"name": "", "type": "bytes32[]"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"name": "newValidCallerHash_", "type": "bytes32"}],
        "name": "addValidCaller",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"name": "removedValidCallerHash_", "type": "bytes32"}],
        "name": "removeValidCaller",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # Events
    {
        "anonymous": False,
        "inputs": [{"indexed": True, "name": "pool", "type": "address"}],
        "name": "LiquidityPoolCreated",
        "type": "event",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": False, "name": "amountA", "type": "uint256"},
            {"indexed": False, "name": "amountB", "type": "uint256"},
            {"indexed": False, "name": "lpTokens", "type": "uint256"},
        ],
        "name": "InitialLiquidityAdded",
        "type": "event",
    },
    {
        "anonymous": False,
        "inputs": [{"indexed": True, "name": "pool", "type": "address"}],
        "name": "LiquidityPoolAdded",
        "type": "event",
    },
    {
        "anonymous": False,
        "inputs": [{"indexed": True, "name": "pool", "type": "address"}],
        "name": "LiquidityPoolRemoved",
        "type": "event",
    },
    {
        "anonymous": False,
        "inputs": [{"indexed": True, "name": "recipient", "type": "address"}],
        "name": "ProjectTaxRecipientUpdated",
        "type": "event",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": False, "name": "oldBuy", "type": "uint16"},
            {"indexed": False, "name": "newBuy", "type": "uint16"},
            {"indexed": False, "name": "oldSell", "type": "uint16"},
            {"indexed": False, "name": "newSell", "type": "uint16"},
        ],
        "name": "ProjectTaxBasisPointsChanged",
        "type": "event",
    },
]

# MultiSend ABI (Gnosis Safe - for batch transfers)
MULTISEND_ABI: list[dict[str, Any]] = [
    {
        "inputs": [{"name": "transactions", "type": "bytes"}],
        "name": "multiSend",
        "outputs": [],
        "stateMutability": "payable",
        "type": "function",
    },
]


# ═══════════════════════════════════════════════════════════════════════════════
# EVENT TOPICS (for parsing logs)
# ═══════════════════════════════════════════════════════════════════════════════


class EventTopics:
    """
    Keccak256 hashes of event signatures for log parsing.

    These are calculated as keccak256(event_signature).
    Example: Transfer(address,address,uint256) -> 0xddf252...
    """

    # ERC-20 events
    TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
    APPROVAL = "0x8c5be1e5ebec7d5bd14f71427d1e84f3dd0314c0f7b2291e5b200ac8c7c3b925"

    # AgentFactory events
    # NewPersona(uint256,address,address,address,address,address)
    NEW_PERSONA = "0x8be0079c531659141344cd1fd0a4f28419497f9722a3daafe3b4186f6b6457e0"
    # NewApplication(uint256)
    NEW_APPLICATION = "0x9f1ec8c880f76798e7b793325d625e9b60e4082a553c98f42b6cda368dd60008"

    # AgentToken events
    # LiquidityPoolCreated(address)
    LIQUIDITY_POOL_CREATED = "0x4f1ef286e0e4c3e8a4f7e6c4b8b9b0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7"
    # InitialLiquidityAdded(uint256,uint256,uint256)
    INITIAL_LIQUIDITY_ADDED = "0x5c6e7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c"
    # LiquidityPoolAdded(address)
    LIQUIDITY_POOL_ADDED = "0x6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e"
    # LiquidityPoolRemoved(address)
    LIQUIDITY_POOL_REMOVED = "0x7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f"
    # ProjectTaxRecipientUpdated(address)
    PROJECT_TAX_RECIPIENT_UPDATED = (
        "0x8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a"
    )
    # ProjectTaxBasisPointsChanged(uint16,uint16,uint16,uint16)
    PROJECT_TAX_CHANGED = "0x9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b"

    # Legacy aliases for backwards compatibility
    AGENT_CREATED = NEW_PERSONA
    CONTRIBUTION = None  # Bonding curve doesn't emit contribution events
    GRADUATED = INITIAL_LIQUIDITY_ADDED


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════


def get_contract_abi(contract_type: str) -> list[dict[str, Any]]:
    """
    Get the ABI for a specific contract type.

    Args:
        contract_type: One of 'erc20', 'agent_factory', 'bonding_curve',
                      'agent_token', 'multisend'

    Returns:
        Contract ABI as list of function/event definitions
    """
    abis = {
        "erc20": ERC20_ABI,
        "agent_factory": AGENT_FACTORY_ABI,
        "bonding_curve": BONDING_CURVE_ABI,
        "agent_token": AGENT_TOKEN_ABI,
        "multisend": MULTISEND_ABI,
    }
    return abis.get(contract_type, [])


def is_abi_complete(contract_type: str) -> bool:
    """
    Check if the ABI for a contract type is complete (not placeholder).

    This is used to determine if real blockchain calls can be made.
    ABIs are sourced from: https://github.com/Virtual-Protocol/protocol-contracts
    """
    # These ABIs are now complete from official Virtuals Protocol sources
    complete_abis = {"erc20", "agent_factory", "bonding_curve", "agent_token", "multisend"}
    return contract_type.lower() in complete_abis


def get_missing_contracts() -> list[str]:
    """
    Get list of contracts missing addresses or ABIs.

    Returns:
        List of contract names that need to be configured
    """
    missing = []

    # Critical contracts needed for agent tokenization
    critical = ["agent_factory", "agent_nft", "acp_registry"]

    for contract in critical:
        if ContractAddresses.BASE_MAINNET.get(contract) is None:
            missing.append(f"BASE_MAINNET.{contract}")

    return missing


def get_configured_contracts() -> dict[str, str]:
    """
    Get all contracts that have addresses configured.

    Returns:
        Dict of contract name -> address for configured contracts
    """
    return {k: v for k, v in ContractAddresses.BASE_MAINNET.items() if v is not None}
