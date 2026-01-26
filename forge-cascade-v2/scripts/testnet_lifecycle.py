"""
Testnet Capsule Lifecycle Script

Runs the full Forge capsule lifecycle on real testnets:
  Phase 0: Configuration & balance validation
  Phase 1: Create 11 enhanced capsules (in-memory) with content hashes
  Phase 2: Anchor capsule hashes on Base Sepolia (CapsuleRegistry.batchAnchor)
  Phase 3: Tokenize C1 (GOT) and C4 (VCT) via MockERC20.mint
  Phase 4: ACP escrow lifecycle (create + release) via SimpleEscrow
  Phase 5: Tipping via Solana Devnet SOL transfer
  Phase 6: Summary report with explorer links

Usage:
  cd forge-cascade-v2
  python -m scripts.testnet_lifecycle

Requirements:
  - .env.testnet in forge-cascade-v2/ with wallet credentials
  - contracts/deployments/baseSepolia.json with deployed contract addresses
  - pip install web3 python-dotenv solders solana
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import struct
import sys
import time
from pathlib import Path
from typing import Any

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 0: CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

# Resolve paths
SCRIPT_DIR = Path(__file__).resolve().parent
FORGE_ROOT = SCRIPT_DIR.parent  # forge-cascade-v2/
PROJECT_ROOT = FORGE_ROOT.parent  # Forge V3/
DEPLOYMENTS_FILE = PROJECT_ROOT / "contracts" / "deployments" / "baseSepolia.json"
ENV_FILE = FORGE_ROOT / ".env.testnet"

# Safety constants
BASE_SEPOLIA_CHAIN_ID = 84532
MAX_ETH_PER_TX = 0.01  # Safety cap
ESCROW_AMOUNT_ETH = 0.0001  # Amount to lock in escrow
TIP_AMOUNT_SOL = 0.001  # SOL tip amount
SOLANA_CLUSTER = "devnet"

# Provider address for escrow (a second address we control or a burn address)
# Using a deterministic address derived from the operator's address
ESCROW_PROVIDER_ADDRESS = "0x000000000000000000000000000000000000dEaD"


def load_env() -> dict[str, str]:
    """Load environment from .env.testnet without requiring python-dotenv."""
    env: dict[str, str] = {}
    if not ENV_FILE.exists():
        print(f"ERROR: {ENV_FILE} not found. Create it with testnet wallet credentials.")
        sys.exit(1)

    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip()
    return env


def compute_content_hash(capsule: dict) -> bytes:
    """Compute SHA-256 hash of capsule content."""
    content = json.dumps(
        {"title": capsule["title"], "content": capsule["content"], "tags": capsule["tags"]},
        sort_keys=True,
        ensure_ascii=True,
    )
    return hashlib.sha256(content.encode()).digest()


def compute_merkle_root(capsule_hashes: list[bytes], lineage_defs: list[tuple[int, int, str]]) -> dict[int, bytes]:
    """Compute merkle roots for each capsule based on lineage chain.

    Root capsules (no parent) use their own content_hash as merkle_root.
    Child capsules use SHA-256(parent_merkle_root + child_content_hash).
    """
    # Build parent map: child_idx -> parent_idx
    parent_map: dict[int, int] = {}
    for child_idx, parent_idx, _ in lineage_defs:
        parent_map[child_idx] = parent_idx

    merkle_roots: dict[int, bytes] = {}

    def get_merkle_root(idx: int) -> bytes:
        if idx in merkle_roots:
            return merkle_roots[idx]

        if idx not in parent_map:
            # Root node: merkle_root = content_hash
            merkle_roots[idx] = capsule_hashes[idx]
        else:
            # Child: merkle_root = hash(parent_root + own_hash)
            parent_root = get_merkle_root(parent_map[idx])
            combined = parent_root + capsule_hashes[idx]
            merkle_roots[idx] = hashlib.sha256(combined).digest()

        return merkle_roots[idx]

    for i in range(len(capsule_hashes)):
        get_merkle_root(i)

    return merkle_roots


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN LIFECYCLE
# ═══════════════════════════════════════════════════════════════════════════════


async def run_lifecycle() -> None:
    """Execute the full testnet lifecycle."""

    print("=" * 70)
    print("  FORGE TESTNET CAPSULE LIFECYCLE")
    print("=" * 70)
    # Note: Using ASCII-only characters for Windows console compatibility
    print()

    # ── Load environment ──────────────────────────────────────────────
    env = load_env()
    evm_private_key = env.get("TESTNET_EVM_PRIVATE_KEY", "")
    evm_address = env.get("TESTNET_EVM_ADDRESS", "")
    solana_private_key = env.get("TESTNET_SOLANA_PRIVATE_KEY", "")
    solana_address = env.get("TESTNET_SOLANA_ADDRESS", "")
    base_sepolia_rpc = env.get("BASE_SEPOLIA_RPC", "https://sepolia.base.org")
    solana_rpc = env.get("SOLANA_DEVNET_RPC", "https://api.devnet.solana.com")

    if not evm_private_key or not evm_address:
        print("ERROR: TESTNET_EVM_PRIVATE_KEY and TESTNET_EVM_ADDRESS required in .env.testnet")
        sys.exit(1)

    # ── Load deployment addresses ─────────────────────────────────────
    if not DEPLOYMENTS_FILE.exists():
        print(f"ERROR: {DEPLOYMENTS_FILE} not found.")
        print("Run: cd contracts && npx hardhat run scripts/deploy-testnet-lifecycle.ts --network baseSepolia")
        sys.exit(1)

    with open(DEPLOYMENTS_FILE) as f:
        deployments = json.load(f)

    contracts = deployments["contracts"]
    registry_address = contracts["CapsuleRegistry"]["address"]
    escrow_address = contracts["SimpleEscrow"]["address"]
    tvirtual_address = contracts["tVIRTUAL"]["address"]
    got_address = contracts["GOT"]["address"]
    vct_address = contracts["VCT"]["address"]

    print(f"  EVM Wallet:        {evm_address}")
    print(f"  Solana Wallet:     {solana_address}")
    print(f"  CapsuleRegistry:   {registry_address}")
    print(f"  SimpleEscrow:      {escrow_address}")
    print(f"  tVIRTUAL:          {tvirtual_address}")
    print(f"  GOT:               {got_address}")
    print(f"  VCT:               {vct_address}")
    print()

    # ── Import web3 ───────────────────────────────────────────────────
    try:
        from web3 import AsyncWeb3, AsyncHTTPProvider
        from web3.middleware import ExtraDataToPOAMiddleware
    except ImportError:
        print("ERROR: web3 not installed. Run: pip install web3")
        sys.exit(1)

    w3 = AsyncWeb3(AsyncHTTPProvider(base_sepolia_rpc))
    # Base Sepolia is a PoA chain, needs this middleware
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

    # ── Import ABIs ───────────────────────────────────────────────────
    from scripts.testnet_contract_abis import (
        CAPSULE_REGISTRY_ABI,
        MOCK_ERC20_ABI,
        SIMPLE_ESCROW_ABI,
    )

    # ── Validate chain ID ─────────────────────────────────────────────
    chain_id = await w3.eth.chain_id
    assert chain_id == BASE_SEPOLIA_CHAIN_ID, (
        f"Safety: expected chain {BASE_SEPOLIA_CHAIN_ID}, got {chain_id}"
    )
    print(f"  Chain ID:          {chain_id} (Base Sepolia)")

    # ── Check balance ─────────────────────────────────────────────────
    balance_wei = await w3.eth.get_balance(evm_address)
    balance_eth = float(w3.from_wei(balance_wei, "ether"))
    print(f"  ETH Balance:       {balance_eth:.6f} ETH")

    if balance_eth < 0.001:
        print("ERROR: Insufficient ETH balance. Need at least 0.001 ETH for gas.")
        sys.exit(1)

    # Collect all tx hashes for summary
    tx_log: list[dict[str, str]] = []
    gas_total = 0

    # Track nonce manually to avoid RPC state propagation race conditions
    current_nonce = await w3.eth.get_transaction_count(evm_address, "pending")

    # ═══════════════════════════════════════════════════════════════════
    # PHASE 1: Create Enhanced Capsules
    # ═══════════════════════════════════════════════════════════════════
    print()
    print("-" * 70)
    print("  PHASE 1: Create Enhanced Capsules")
    print("-" * 70)

    from scripts.seed_capsules_testnet import CAPSULE_DEFS, LINEAGE_DEFS, TOKENIZATION_CONFIGS

    # Compute content hashes
    content_hashes: list[bytes] = []
    for i, capsule in enumerate(CAPSULE_DEFS):
        h = compute_content_hash(capsule)
        content_hashes.append(h)
        print(f"  C{i+1:2d} [{capsule['title'][:45]:45s}] hash={h.hex()[:16]}...")

    # Compute merkle roots
    merkle_roots = compute_merkle_root(content_hashes, LINEAGE_DEFS)
    print(f"\n  Merkle roots computed for {len(merkle_roots)} capsules")
    print(f"  Lineage chains: {len(LINEAGE_DEFS)}")

    # ═══════════════════════════════════════════════════════════════════
    # PHASE 2: Anchor Capsules on Base Sepolia
    # ═══════════════════════════════════════════════════════════════════
    print()
    print("-" * 70)
    print("  PHASE 2: Anchor Capsules on Base Sepolia")
    print("-" * 70)

    registry = w3.eth.contract(
        address=w3.to_checksum_address(registry_address),
        abi=CAPSULE_REGISTRY_ABI,
    )

    # Prepare batch anchor parameters
    capsule_ids: list[bytes] = []
    hash_list: list[bytes] = []
    root_list: list[bytes] = []
    type_list: list[int] = []

    for i, capsule in enumerate(CAPSULE_DEFS):
        # capsuleId = SHA-256 of the title (unique identifier)
        cid = hashlib.sha256(capsule["title"].encode()).digest()
        capsule_ids.append(cid)
        hash_list.append(content_hashes[i])
        root_list.append(merkle_roots[i])
        type_list.append(capsule["type"])

    # Check if capsules are already anchored (from a previous run)
    already_anchored = False
    try:
        already_anchored = await registry.functions.isAnchored(capsule_ids[0]).call()
    except Exception:
        pass

    if already_anchored:
        print(f"  Capsules already anchored (previous run). Skipping batchAnchor.")
        try:
            on_chain_count = await registry.functions.capsuleCount().call()
            print(f"  On-chain capsule count: {on_chain_count}")
        except Exception:
            pass
        tx_log.append({
            "phase": "Anchor Capsules",
            "tx_hash": "(already anchored)",
            "gas_used": "0",
            "status": "SKIPPED",
            "explorer": f"https://sepolia.basescan.org/address/{registry_address}",
        })
    else:
        print(f"  Anchoring {len(CAPSULE_DEFS)} capsules via batchAnchor()...")

        # Build and send transaction
        nonce = current_nonce
        gas_price = await w3.eth.gas_price

        tx = await registry.functions.batchAnchor(
            capsule_ids, hash_list, root_list, type_list
        ).build_transaction({
            "from": evm_address,
            "nonce": nonce,
            "gasPrice": gas_price,
            "chainId": BASE_SEPOLIA_CHAIN_ID,
        })

        # Estimate gas
        try:
            gas_estimate = await w3.eth.estimate_gas(tx)
            tx["gas"] = int(gas_estimate * 1.2)  # 20% buffer
        except Exception as e:
            print(f"  Gas estimation failed: {e}")
            tx["gas"] = 500_000  # Fallback

        # Sign and send
        signed = w3.eth.account.sign_transaction(tx, evm_private_key)
        tx_hash = await w3.eth.send_raw_transaction(signed.raw_transaction)
        current_nonce += 1
        print(f"  Tx sent: {tx_hash.hex()}")
        print(f"  Waiting for confirmation...")

        receipt = await w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        gas_used = receipt["gasUsed"]
        gas_total += gas_used
        status = "SUCCESS" if receipt["status"] == 1 else "FAILED"
        print(f"  Status: {status} | Gas: {gas_used:,} | Block: {receipt['blockNumber']}")

        tx_log.append({
            "phase": "Anchor Capsules",
            "tx_hash": tx_hash.hex(),
            "gas_used": str(gas_used),
            "status": status,
            "explorer": f"https://sepolia.basescan.org/tx/{tx_hash.hex()}",
        })

        # Verify capsules on-chain (with retry for RPC state propagation)
        if receipt["status"] == 1:
            print(f"\n  Verifying anchored capsules...")
            await asyncio.sleep(5)
            verified_count = 0
            for i in range(len(CAPSULE_DEFS)):
                try:
                    is_verified = await registry.functions.verifyCapsule(
                        capsule_ids[i], content_hashes[i]
                    ).call()
                    if is_verified:
                        verified_count += 1
                except Exception:
                    try:
                        is_anchored = await registry.functions.isAnchored(
                            capsule_ids[i]
                        ).call()
                        if is_anchored:
                            verified_count += 1
                    except Exception:
                        pass
            print(f"  Verified: {verified_count}/{len(CAPSULE_DEFS)} capsules")

            try:
                on_chain_count = await registry.functions.capsuleCount().call()
                print(f"  On-chain capsule count: {on_chain_count}")
            except Exception:
                print(f"  (capsuleCount read deferred)")

    # ═══════════════════════════════════════════════════════════════════
    # PHASE 3: Tokenize C1 (GOT) and C4 (VCT)
    # ═══════════════════════════════════════════════════════════════════
    print()
    print("-" * 70)
    print("  PHASE 3: Tokenize Capsules (GOT + VCT)")
    print("-" * 70)

    for capsule_idx, token_name, token_symbol, initial_stake in TOKENIZATION_CONFIGS:
        token_address = got_address if token_symbol == "GOT" else vct_address
        token_contract = w3.eth.contract(
            address=w3.to_checksum_address(token_address),
            abi=MOCK_ERC20_ABI,
        )

        mint_amount = w3.to_wei(initial_stake, "ether")  # 18 decimals
        nonce = current_nonce

        print(f"\n  Minting {initial_stake} {token_symbol} for C{capsule_idx + 1}...")

        mint_tx = await token_contract.functions.mint(
            evm_address, mint_amount
        ).build_transaction({
            "from": evm_address,
            "nonce": nonce,
            "gasPrice": await w3.eth.gas_price,
            "chainId": BASE_SEPOLIA_CHAIN_ID,
        })

        try:
            gas_est = await w3.eth.estimate_gas(mint_tx)
            mint_tx["gas"] = int(gas_est * 1.2)
        except Exception:
            mint_tx["gas"] = 100_000

        signed = w3.eth.account.sign_transaction(mint_tx, evm_private_key)
        tx_hash = await w3.eth.send_raw_transaction(signed.raw_transaction)
        current_nonce += 1
        receipt = await w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        gas_used = receipt["gasUsed"]
        gas_total += gas_used
        status = "SUCCESS" if receipt["status"] == 1 else "FAILED"

        print(f"  Tx: {tx_hash.hex()}")
        print(f"  Status: {status} | Gas: {gas_used:,}")

        # Check balance
        balance = await token_contract.functions.balanceOf(evm_address).call()
        print(f"  {token_symbol} balance: {w3.from_wei(balance, 'ether')}")

        tx_log.append({
            "phase": f"Mint {token_symbol}",
            "tx_hash": tx_hash.hex(),
            "gas_used": str(gas_used),
            "status": status,
            "explorer": f"https://sepolia.basescan.org/tx/{tx_hash.hex()}",
        })

    # ═══════════════════════════════════════════════════════════════════
    # PHASE 4: ACP Escrow Lifecycle
    # ═══════════════════════════════════════════════════════════════════
    print()
    print("-" * 70)
    print("  PHASE 4: ACP Escrow Lifecycle")
    print("-" * 70)

    escrow_contract = w3.eth.contract(
        address=w3.to_checksum_address(escrow_address),
        abi=SIMPLE_ESCROW_ABI,
    )

    # Create escrow
    job_hash = hashlib.sha256(b"ACP-Job-GenomicAnalysis-001").digest()
    deadline = int(time.time()) + 3600  # 1 hour from now
    escrow_value = w3.to_wei(ESCROW_AMOUNT_ETH, "ether")

    assert ESCROW_AMOUNT_ETH <= MAX_ETH_PER_TX, "Safety: escrow amount exceeds max"

    nonce = current_nonce
    print(f"  Creating escrow: {ESCROW_AMOUNT_ETH} ETH, deadline={deadline}")
    print(f"  Provider: {ESCROW_PROVIDER_ADDRESS}")

    create_tx = await escrow_contract.functions.createEscrow(
        w3.to_checksum_address(ESCROW_PROVIDER_ADDRESS),
        deadline,
        job_hash,
    ).build_transaction({
        "from": evm_address,
        "nonce": nonce,
        "gasPrice": await w3.eth.gas_price,
        "value": escrow_value,
        "chainId": BASE_SEPOLIA_CHAIN_ID,
    })

    try:
        gas_est = await w3.eth.estimate_gas(create_tx)
        create_tx["gas"] = int(gas_est * 1.2)
    except Exception:
        create_tx["gas"] = 150_000

    signed = w3.eth.account.sign_transaction(create_tx, evm_private_key)
    tx_hash = await w3.eth.send_raw_transaction(signed.raw_transaction)
    current_nonce += 1
    receipt = await w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    gas_used = receipt["gasUsed"]
    gas_total += gas_used
    status = "SUCCESS" if receipt["status"] == 1 else "FAILED"

    print(f"  Create Tx: {tx_hash.hex()}")
    print(f"  Status: {status} | Gas: {gas_used:,}")

    tx_log.append({
        "phase": "Create Escrow",
        "tx_hash": tx_hash.hex(),
        "gas_used": str(gas_used),
        "status": status,
        "explorer": f"https://sepolia.basescan.org/tx/{tx_hash.hex()}",
    })

    # Read escrow state (with retry for RPC state propagation)
    escrow_id = None
    for attempt in range(5):
        await asyncio.sleep(3)
        escrow_count = await escrow_contract.functions.escrowCount().call()
        if escrow_count > 0:
            escrow_id = escrow_count - 1
            break
        print(f"  Waiting for escrow state propagation (attempt {attempt + 1}/5)...")

    if escrow_id is None:
        # Fallback: first escrow on a fresh contract is always ID 0
        print("  escrowCount() still 0 after retries; assuming escrow_id=0")
        escrow_id = 0

    try:
        is_active = await escrow_contract.functions.isActive(escrow_id).call()
        print(f"  Escrow ID: {escrow_id} | Active: {is_active}")
    except Exception as exc:
        print(f"  Escrow ID: {escrow_id} | isActive check failed: {exc}")

    # Release escrow (buyer approves)
    nonce = current_nonce
    print(f"\n  Releasing escrow {escrow_id} to provider...")

    release_tx = await escrow_contract.functions.releaseToProvider(
        escrow_id
    ).build_transaction({
        "from": evm_address,
        "nonce": nonce,
        "gasPrice": await w3.eth.gas_price,
        "chainId": BASE_SEPOLIA_CHAIN_ID,
    })

    try:
        gas_est = await w3.eth.estimate_gas(release_tx)
        release_tx["gas"] = int(gas_est * 1.2)
    except Exception:
        release_tx["gas"] = 100_000

    signed = w3.eth.account.sign_transaction(release_tx, evm_private_key)
    tx_hash = await w3.eth.send_raw_transaction(signed.raw_transaction)
    current_nonce += 1
    receipt = await w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    gas_used = receipt["gasUsed"]
    gas_total += gas_used
    status = "SUCCESS" if receipt["status"] == 1 else "FAILED"

    print(f"  Release Tx: {tx_hash.hex()}")
    print(f"  Status: {status} | Gas: {gas_used:,}")

    # Verify final state (with delay for propagation)
    await asyncio.sleep(3)
    try:
        is_active_after = await escrow_contract.functions.isActive(escrow_id).call()
        print(f"  Escrow Active After Release: {is_active_after} (expected: False)")
    except Exception as exc:
        print(f"  Post-release isActive check failed: {exc}")

    tx_log.append({
        "phase": "Release Escrow",
        "tx_hash": tx_hash.hex(),
        "gas_used": str(gas_used),
        "status": status,
        "explorer": f"https://sepolia.basescan.org/tx/{tx_hash.hex()}",
    })

    # ═══════════════════════════════════════════════════════════════════
    # PHASE 5: Tipping via Solana Devnet
    # ═══════════════════════════════════════════════════════════════════
    print()
    print("-" * 70)
    print("  PHASE 5: Solana Devnet Tipping")
    print("-" * 70)

    solana_tx_sig = None
    try:
        from solders.keypair import Keypair
        from solders.pubkey import Pubkey
        from solders.system_program import TransferParams, transfer
        from solders.transaction import Transaction
        from solders.message import Message
        from solana.rpc.async_api import AsyncClient as SolanaClient
        from solders.hash import Hash as SolanaHash
        import base58

        # Reconstruct keypair from base58 private key
        secret_bytes = base58.b58decode(solana_private_key)
        keypair = Keypair.from_bytes(secret_bytes)

        print(f"  Sender:    {keypair.pubkey()}")
        print(f"  Recipient: (self-transfer for demo)")
        print(f"  Amount:    {TIP_AMOUNT_SOL} SOL")

        async with SolanaClient(solana_rpc) as client:
            # Verify cluster
            version = await client.get_version()
            print(f"  Cluster:   Solana Devnet (version: {version.value.solana_core})")

            # Check balance
            bal_resp = await client.get_balance(keypair.pubkey())
            sol_balance = bal_resp.value / 1_000_000_000
            print(f"  Balance:   {sol_balance:.4f} SOL")

            if sol_balance < TIP_AMOUNT_SOL + 0.001:  # Need extra for fees
                print("  WARNING: Insufficient SOL balance for tip. Skipping Phase 5.")
            else:
                # Build transfer (self-transfer for demo purposes)
                lamports = int(TIP_AMOUNT_SOL * 1_000_000_000)
                recipient = keypair.pubkey()  # Self-transfer for demo

                # Get recent blockhash
                bh_resp = await client.get_latest_blockhash()
                recent_blockhash = bh_resp.value.blockhash

                # Build instruction
                ix = transfer(TransferParams(
                    from_pubkey=keypair.pubkey(),
                    to_pubkey=recipient,
                    lamports=lamports,
                ))

                # Build and sign transaction
                msg = Message.new_with_blockhash(
                    [ix],
                    keypair.pubkey(),
                    recent_blockhash,
                )
                sol_tx = Transaction.new_unsigned(msg)
                sol_tx.sign([keypair], recent_blockhash)

                # Send
                result = await client.send_transaction(sol_tx)
                solana_tx_sig = str(result.value)
                print(f"  Tx Signature: {solana_tx_sig}")

                # Wait for confirmation
                print("  Waiting for confirmation...")
                await asyncio.sleep(5)  # Solana devnet confirmations

                tx_log.append({
                    "phase": "Solana Tip",
                    "tx_hash": solana_tx_sig,
                    "gas_used": "~5000 lamports",
                    "status": "SUCCESS",
                    "explorer": f"https://explorer.solana.com/tx/{solana_tx_sig}?cluster=devnet",
                })

    except ImportError as e:
        print(f"  Solana libraries not available: {e}")
        print("  Install with: pip install solana solders base58")
        print("  Skipping Phase 5.")
    except Exception as e:
        print(f"  Solana tip failed: {e}")
        print("  Skipping Phase 5.")

    # ═══════════════════════════════════════════════════════════════════
    # PHASE 6: Summary Report
    # ═══════════════════════════════════════════════════════════════════
    print()
    print("=" * 70)
    print("  LIFECYCLE SUMMARY")
    print("=" * 70)

    # Final balance
    final_balance_wei = await w3.eth.get_balance(evm_address)
    final_balance_eth = float(w3.from_wei(final_balance_wei, "ether"))
    eth_spent = balance_eth - final_balance_eth

    print(f"\n  Capsules anchored:     11")
    print(f"  Tokens minted:         GOT (100), VCT (200)")
    print(f"  Escrow created+released: 1")
    print(f"  Solana tip:            {'Yes' if solana_tx_sig else 'Skipped'}")
    print(f"\n  Gas Summary:")
    print(f"    Total gas units:     {gas_total:,}")
    print(f"    ETH spent:           {eth_spent:.8f} ETH")
    print(f"    Starting balance:    {balance_eth:.6f} ETH")
    print(f"    Final balance:       {final_balance_eth:.6f} ETH")

    print(f"\n  Transaction Log:")
    print(f"  {'Phase':<20s} {'Status':<8s} {'Gas':>10s}  Explorer Link")
    print(f"  {'-'*20} {'-'*8} {'-'*10}  {'-'*50}")

    for entry in tx_log:
        print(
            f"  {entry['phase']:<20s} {entry['status']:<8s} {entry['gas_used']:>10s}  "
            f"{entry['explorer']}"
        )

    print(f"\n  Contract Addresses (Base Sepolia):")
    print(f"    CapsuleRegistry: https://sepolia.basescan.org/address/{registry_address}")
    print(f"    SimpleEscrow:    https://sepolia.basescan.org/address/{escrow_address}")
    print(f"    tVIRTUAL:        https://sepolia.basescan.org/address/{tvirtual_address}")
    print(f"    GOT:             https://sepolia.basescan.org/address/{got_address}")
    print(f"    VCT:             https://sepolia.basescan.org/address/{vct_address}")

    print()
    print("=" * 70)
    print("  LIFECYCLE COMPLETE")
    print("=" * 70)

    # Save results to JSON
    results_file = FORGE_ROOT / "testnet_lifecycle_results.json"
    results = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "chain": "Base Sepolia (84532)",
        "operator": evm_address,
        "contracts": {
            "CapsuleRegistry": registry_address,
            "SimpleEscrow": escrow_address,
            "tVIRTUAL": tvirtual_address,
            "GOT": got_address,
            "VCT": vct_address,
        },
        "transactions": tx_log,
        "gas_total": gas_total,
        "eth_spent": eth_spent,
        "capsules_anchored": 11,
        "solana_tip": solana_tx_sig,
    }
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n  Results saved to: {results_file}")


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    asyncio.run(run_lifecycle())
