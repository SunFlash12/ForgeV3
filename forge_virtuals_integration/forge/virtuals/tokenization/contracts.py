"""
Virtuals Protocol Smart Contract ABIs and Addresses

This module contains the contract ABIs and addresses needed for blockchain
interactions with Virtuals Protocol.

IMPORTANT: The ABIs and addresses must be obtained from the official
Virtuals Protocol documentation or deployment records.

Contract Documentation:
- AgentFactory: Creates new agent tokens with bonding curves
- BondingCurve: Manages token bonding curve contributions
- VIRTUAL Token: The native VIRTUAL token (ERC-20)
- MultiSend: Batch transfer utility for gas-efficient distributions

To complete integration:
1. Obtain ABIs from https://docs.virtuals.io/developers/contracts
2. Verify contract addresses on Base/Ethereum block explorers
3. Run test transactions on Base Sepolia before mainnet
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

    # Base Mainnet
    BASE_MAINNET = {
        "virtual_token": "0x0b3e328455c4059EEb9e3f84b5543F74E24e7E1b",
        "agent_factory": None,  # TODO: Get from Virtuals Protocol docs
        "agent_nft": None,  # TODO: Get from Virtuals Protocol docs
        "acp_registry": None,  # TODO: Get from Virtuals Protocol docs
        "vault": "0xdAd686299FB562f89e55DA05F1D96FaBEb2A2E32",
        "bridge": "0x3154Cf16ccdb4C6d922629664174b904d80F2C35",
        "multisend": "0x40A2aCCbd92BCA938b02010E17A5b8929b49130D",  # Gnosis Safe MultiSend
    }

    # Base Sepolia (Testnet)
    BASE_SEPOLIA = {
        "virtual_token": None,  # TODO: Get testnet deployment
        "agent_factory": None,
        "agent_nft": None,
        "acp_registry": None,
        "vault": None,
        "bridge": None,
        "multisend": "0x40A2aCCbd92BCA938b02010E17A5b8929b49130D",
    }

    # Ethereum Mainnet
    ETHEREUM_MAINNET = {
        "virtual_token": "0x44ff8620b8cA30902395A7bD3F2407e1A091BF73",
        "bridge": "0x3154Cf16ccdb4C6d922629664174b904d80F2C35",
    }

    # Solana Mainnet
    SOLANA_MAINNET = {
        "virtual_token": "3iQL8BFS2vE7mww4ehAqQHAsbmRNCrPxizWAT2Zfyr9y",
    }

    @classmethod
    def get_address(cls, chain: str, contract: str) -> str | None:
        """Get a contract address for a specific chain."""
        chain_map = {
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
        "type": "function"
    },
    {
        "inputs": [
            {"name": "spender", "type": "address"},
            {"name": "amount", "type": "uint256"}
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"name": "owner", "type": "address"},
            {"name": "spender", "type": "address"}
        ],
        "name": "allowance",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"name": "recipient", "type": "address"},
            {"name": "amount", "type": "uint256"}
        ],
        "name": "transfer",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"name": "sender", "type": "address"},
            {"name": "recipient", "type": "address"},
            {"name": "amount", "type": "uint256"}
        ],
        "name": "transferFrom",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "totalSupply",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
]

# AgentFactory ABI (for creating new agent tokens)
# TODO: Replace with actual ABI from Virtuals Protocol
AGENT_FACTORY_ABI: list[dict[str, Any]] = [
    # createAgent - Creates a new agent token with bonding curve
    {
        "inputs": [
            {"name": "name", "type": "string"},
            {"name": "symbol", "type": "string"},
            {"name": "initialStake", "type": "uint256"}
        ],
        "name": "createAgent",
        "outputs": [{"name": "tokenAddress", "type": "address"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    # AgentCreated event - Emitted when new agent is created
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "tokenAddress", "type": "address"},
            {"indexed": True, "name": "creator", "type": "address"},
            {"indexed": False, "name": "name", "type": "string"},
            {"indexed": False, "name": "symbol", "type": "string"},
            {"indexed": False, "name": "initialStake", "type": "uint256"}
        ],
        "name": "AgentCreated",
        "type": "event"
    },
    # getAgentInfo - Get info about an agent token
    {
        "inputs": [{"name": "tokenAddress", "type": "address"}],
        "name": "getAgentInfo",
        "outputs": [
            {"name": "name", "type": "string"},
            {"name": "symbol", "type": "string"},
            {"name": "creator", "type": "address"},
            {"name": "totalRaised", "type": "uint256"},
            {"name": "isGraduated", "type": "bool"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
]

# BondingCurve ABI (for contributing to bonding curve)
# TODO: Replace with actual ABI from Virtuals Protocol
BONDING_CURVE_ABI: list[dict[str, Any]] = [
    # contribute - Contribute VIRTUAL to bonding curve
    {
        "inputs": [{"name": "amount", "type": "uint256"}],
        "name": "contribute",
        "outputs": [{"name": "tokensReceived", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    # Contribution event
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "contributor", "type": "address"},
            {"indexed": False, "name": "virtualAmount", "type": "uint256"},
            {"indexed": False, "name": "tokensReceived", "type": "uint256"}
        ],
        "name": "Contribution",
        "type": "event"
    },
    # getCurrentPrice - Get current bonding curve price
    {
        "inputs": [],
        "name": "getCurrentPrice",
        "outputs": [{"name": "price", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    # getTotalRaised - Get total VIRTUAL raised
    {
        "inputs": [],
        "name": "getTotalRaised",
        "outputs": [{"name": "total", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    # getGraduationThreshold - Get threshold for graduation
    {
        "inputs": [],
        "name": "getGraduationThreshold",
        "outputs": [{"name": "threshold", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    # isGraduated - Check if token has graduated
    {
        "inputs": [],
        "name": "isGraduated",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function"
    },
]

# Token ABI (for graduated agent tokens)
# TODO: Replace with actual ABI from Virtuals Protocol
AGENT_TOKEN_ABI: list[dict[str, Any]] = ERC20_ABI + [
    # graduate - Graduate token from bonding curve to Uniswap
    {
        "inputs": [],
        "name": "graduate",
        "outputs": [{"name": "poolAddress", "type": "address"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    # Graduated event
    {
        "anonymous": False,
        "inputs": [
            {"indexed": False, "name": "poolAddress", "type": "address"},
            {"indexed": False, "name": "liquidity", "type": "uint256"},
            {"indexed": False, "name": "virtualLocked", "type": "uint256"}
        ],
        "name": "Graduated",
        "type": "event"
    },
    # getPool - Get Uniswap pool address (after graduation)
    {
        "inputs": [],
        "name": "getPool",
        "outputs": [{"name": "pool", "type": "address"}],
        "stateMutability": "view",
        "type": "function"
    },
]

# MultiSend ABI (Gnosis Safe - for batch transfers)
MULTISEND_ABI: list[dict[str, Any]] = [
    {
        "inputs": [{"name": "transactions", "type": "bytes"}],
        "name": "multiSend",
        "outputs": [],
        "stateMutability": "payable",
        "type": "function"
    },
]


# ═══════════════════════════════════════════════════════════════════════════════
# EVENT TOPICS (for parsing logs)
# ═══════════════════════════════════════════════════════════════════════════════

class EventTopics:
    """Keccak256 hashes of event signatures for log parsing."""

    # ERC-20 events
    TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
    APPROVAL = "0x8c5be1e5ebec7d5bd14f71427d1e84f3dd0314c0f7b2291e5b200ac8c7c3b925"

    # AgentFactory events (placeholder - update with actual topic hashes)
    AGENT_CREATED = None  # TODO: Calculate from event signature

    # BondingCurve events (placeholder)
    CONTRIBUTION = None  # TODO: Calculate from event signature

    # Token events (placeholder)
    GRADUATED = None  # TODO: Calculate from event signature


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
    """
    # TODO: Implement actual check once real ABIs are available
    # For now, return False to indicate ABIs need to be obtained
    return False


def get_missing_contracts() -> list[str]:
    """
    Get list of contracts missing addresses or ABIs.

    Returns:
        List of contract names that need to be configured
    """
    missing = []

    # Check Base mainnet addresses
    for contract, address in ContractAddresses.BASE_MAINNET.items():
        if address is None:
            missing.append(f"BASE_MAINNET.{contract}")

    return missing
