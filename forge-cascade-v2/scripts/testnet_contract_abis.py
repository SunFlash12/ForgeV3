"""
Contract ABI Definitions for Testnet Lifecycle

Minimal ABIs extracted from Hardhat compilation artifacts for:
  - CapsuleRegistry: on-chain capsule hash anchoring
  - SimpleEscrow: ETH-based ACP job escrow
  - MockERC20: test token minting

Only includes functions used by the lifecycle script.
"""

from __future__ import annotations

# ═══════════════════════════════════════════════════════════════════════════════
# CapsuleRegistry ABI
# ═══════════════════════════════════════════════════════════════════════════════

CAPSULE_REGISTRY_ABI = [
    {
        "inputs": [],
        "stateMutability": "nonpayable",
        "type": "constructor",
    },
    # anchorCapsule(bytes32, bytes32, bytes32, uint8)
    {
        "inputs": [
            {"internalType": "bytes32", "name": "capsuleId", "type": "bytes32"},
            {"internalType": "bytes32", "name": "contentHash", "type": "bytes32"},
            {"internalType": "bytes32", "name": "merkleRoot", "type": "bytes32"},
            {"internalType": "uint8", "name": "capsuleType", "type": "uint8"},
        ],
        "name": "anchorCapsule",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # batchAnchor(bytes32[], bytes32[], bytes32[], uint8[])
    {
        "inputs": [
            {"internalType": "bytes32[]", "name": "capsuleIds", "type": "bytes32[]"},
            {"internalType": "bytes32[]", "name": "contentHashes", "type": "bytes32[]"},
            {"internalType": "bytes32[]", "name": "merkleRoots", "type": "bytes32[]"},
            {"internalType": "uint8[]", "name": "capsuleTypes", "type": "uint8[]"},
        ],
        "name": "batchAnchor",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # verifyCapsule(bytes32, bytes32) -> bool
    {
        "inputs": [
            {"internalType": "bytes32", "name": "capsuleId", "type": "bytes32"},
            {"internalType": "bytes32", "name": "contentHash", "type": "bytes32"},
        ],
        "name": "verifyCapsule",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function",
    },
    # getCapsule(bytes32) -> CapsuleRecord
    {
        "inputs": [
            {"internalType": "bytes32", "name": "capsuleId", "type": "bytes32"},
        ],
        "name": "getCapsule",
        "outputs": [
            {
                "components": [
                    {"internalType": "bytes32", "name": "contentHash", "type": "bytes32"},
                    {"internalType": "bytes32", "name": "merkleRoot", "type": "bytes32"},
                    {"internalType": "uint8", "name": "capsuleType", "type": "uint8"},
                    {"internalType": "uint256", "name": "anchoredAt", "type": "uint256"},
                    {"internalType": "address", "name": "anchoredBy", "type": "address"},
                ],
                "internalType": "struct CapsuleRegistry.CapsuleRecord",
                "name": "",
                "type": "tuple",
            }
        ],
        "stateMutability": "view",
        "type": "function",
    },
    # isAnchored(bytes32) -> bool
    {
        "inputs": [
            {"internalType": "bytes32", "name": "capsuleId", "type": "bytes32"},
        ],
        "name": "isAnchored",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function",
    },
    # capsuleCount() -> uint256
    {
        "inputs": [],
        "name": "capsuleCount",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    # Events
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "bytes32", "name": "capsuleId", "type": "bytes32"},
            {"indexed": False, "internalType": "bytes32", "name": "contentHash", "type": "bytes32"},
            {"indexed": False, "internalType": "bytes32", "name": "merkleRoot", "type": "bytes32"},
            {"indexed": False, "internalType": "uint8", "name": "capsuleType", "type": "uint8"},
            {"indexed": True, "internalType": "address", "name": "anchoredBy", "type": "address"},
            {"indexed": False, "internalType": "uint256", "name": "timestamp", "type": "uint256"},
        ],
        "name": "CapsuleAnchored",
        "type": "event",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": False, "internalType": "uint256", "name": "count", "type": "uint256"},
            {"indexed": True, "internalType": "address", "name": "anchoredBy", "type": "address"},
            {"indexed": False, "internalType": "uint256", "name": "timestamp", "type": "uint256"},
        ],
        "name": "BatchAnchored",
        "type": "event",
    },
]

# ═══════════════════════════════════════════════════════════════════════════════
# SimpleEscrow ABI
# ═══════════════════════════════════════════════════════════════════════════════

SIMPLE_ESCROW_ABI = [
    # createEscrow(address, uint256, bytes32) -> uint256
    {
        "inputs": [
            {"internalType": "address", "name": "provider", "type": "address"},
            {"internalType": "uint256", "name": "deadline", "type": "uint256"},
            {"internalType": "bytes32", "name": "jobHash", "type": "bytes32"},
        ],
        "name": "createEscrow",
        "outputs": [{"internalType": "uint256", "name": "escrowId", "type": "uint256"}],
        "stateMutability": "payable",
        "type": "function",
    },
    # releaseToProvider(uint256)
    {
        "inputs": [
            {"internalType": "uint256", "name": "escrowId", "type": "uint256"},
        ],
        "name": "releaseToProvider",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # refundToBuyer(uint256)
    {
        "inputs": [
            {"internalType": "uint256", "name": "escrowId", "type": "uint256"},
        ],
        "name": "refundToBuyer",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # getEscrow(uint256) -> Escrow
    {
        "inputs": [
            {"internalType": "uint256", "name": "escrowId", "type": "uint256"},
        ],
        "name": "getEscrow",
        "outputs": [
            {
                "components": [
                    {"internalType": "address", "name": "buyer", "type": "address"},
                    {"internalType": "address", "name": "provider", "type": "address"},
                    {"internalType": "uint256", "name": "amount", "type": "uint256"},
                    {"internalType": "uint256", "name": "deadline", "type": "uint256"},
                    {"internalType": "bytes32", "name": "jobHash", "type": "bytes32"},
                    {"internalType": "uint8", "name": "state", "type": "uint8"},
                    {"internalType": "uint256", "name": "createdAt", "type": "uint256"},
                ],
                "internalType": "struct SimpleEscrow.Escrow",
                "name": "",
                "type": "tuple",
            }
        ],
        "stateMutability": "view",
        "type": "function",
    },
    # isActive(uint256) -> bool
    {
        "inputs": [
            {"internalType": "uint256", "name": "escrowId", "type": "uint256"},
        ],
        "name": "isActive",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function",
    },
    # escrowCount() -> uint256
    {
        "inputs": [],
        "name": "escrowCount",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    # Events
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "uint256", "name": "escrowId", "type": "uint256"},
            {"indexed": True, "internalType": "address", "name": "buyer", "type": "address"},
            {"indexed": True, "internalType": "address", "name": "provider", "type": "address"},
            {"indexed": False, "internalType": "uint256", "name": "amount", "type": "uint256"},
            {"indexed": False, "internalType": "uint256", "name": "deadline", "type": "uint256"},
            {"indexed": False, "internalType": "bytes32", "name": "jobHash", "type": "bytes32"},
        ],
        "name": "EscrowCreated",
        "type": "event",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "uint256", "name": "escrowId", "type": "uint256"},
            {"indexed": True, "internalType": "address", "name": "provider", "type": "address"},
            {"indexed": False, "internalType": "uint256", "name": "amount", "type": "uint256"},
        ],
        "name": "EscrowReleased",
        "type": "event",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "uint256", "name": "escrowId", "type": "uint256"},
            {"indexed": True, "internalType": "address", "name": "buyer", "type": "address"},
            {"indexed": False, "internalType": "uint256", "name": "amount", "type": "uint256"},
        ],
        "name": "EscrowRefunded",
        "type": "event",
    },
]

# ═══════════════════════════════════════════════════════════════════════════════
# MockERC20 ABI (mint only — standard ERC-20 read functions handled by web3)
# ═══════════════════════════════════════════════════════════════════════════════

MOCK_ERC20_ABI = [
    # mint(address, uint256)
    {
        "inputs": [
            {"internalType": "address", "name": "to", "type": "address"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"},
        ],
        "name": "mint",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # balanceOf(address) -> uint256
    {
        "inputs": [
            {"internalType": "address", "name": "account", "type": "address"},
        ],
        "name": "balanceOf",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    # name() -> string
    {
        "inputs": [],
        "name": "name",
        "outputs": [{"internalType": "string", "name": "", "type": "string"}],
        "stateMutability": "view",
        "type": "function",
    },
    # symbol() -> string
    {
        "inputs": [],
        "name": "symbol",
        "outputs": [{"internalType": "string", "name": "", "type": "string"}],
        "stateMutability": "view",
        "type": "function",
    },
    # totalSupply() -> uint256
    {
        "inputs": [],
        "name": "totalSupply",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
]
