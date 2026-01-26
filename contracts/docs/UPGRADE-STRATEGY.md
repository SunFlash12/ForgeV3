# Smart Contract Upgrade Strategy

## Design Decision: Non-Upgradeable Contracts

All Forge smart contracts are deployed as **non-upgradeable** (no proxy pattern). This is an intentional design choice for the following reasons:

### CapsuleRegistry

**Rationale**: Immutable by design. The registry's purpose is to provide an immutable on-chain record of capsule content hashes. If the registry itself could be upgraded, it would undermine the integrity guarantee that content hashes are permanent and tamper-proof.

**Migration path**: If a new version is needed:
1. Deploy `CapsuleRegistryV2` alongside the existing registry
2. Both registries remain valid — old anchored hashes are never invalidated
3. Update off-chain indexers to read from both contracts
4. New capsules are anchored in V2 only

### SimpleEscrow

**Rationale**: Each escrow is an independent unit with a finite lifecycle (Active -> Released/Refunded). There is no shared state that would benefit from upgradeability.

**Migration path**: If a new version is needed:
1. Deploy `SimpleEscrowV2` alongside the existing escrow
2. Existing active escrows continue to resolve on V1 (release or refund)
3. New escrows are created on V2 only
4. V1 naturally drains as all escrows complete
5. The `maxEscrowAmount` is owner-configurable — set to 0 on V1 to prevent new escrows if desired

### CapsuleMarketplace

**Rationale**: The marketplace holds no long-term token balances (all distributions happen atomically in `purchaseCapsule`). Listings are cheap to recreate.

**Migration path**: If a new version is needed:
1. Pause V1 marketplace (`pause()`)
2. Deploy V2 with updated logic
3. Sellers recreate listings on V2
4. The `emergencyWithdraw()` function recovers any stuck tokens from V1

## Emergency Procedures

### Pause Mechanism

All contracts support emergency pause:
- **CapsuleRegistry**: `pause()` / `unpause()` (owner only) — blocks new anchoring while allowing reads
- **SimpleEscrow**: `pause()` / `unpause()` (owner only) — blocks new escrow creation while allowing existing escrows to resolve
- **CapsuleMarketplace**: `pause()` / `unpause()` (owner only) — already implemented

### Owner Key Security

- The deployer/owner address controls all admin functions
- For mainnet: use a hardware wallet or multisig (e.g., Gnosis Safe)
- Owner can transfer ownership via OpenZeppelin's `transferOwnership()`
- Two-step ownership transfer recommended (accept pattern)

## Versioning

Contract versions are tracked by deployment, not by proxy slots:

| Contract | Testnet (Base Sepolia) | Mainnet (Base) |
|----------|----------------------|----------------|
| CapsuleRegistry | `0x6C42f2DaA3Cf1E63E8C1d6eaB74A4Af32948bC34` | Not yet deployed |
| SimpleEscrow | `0x0E661dCfd4d0c7C167198aA01B56Ec48f620bB8d` | Not yet deployed |
| CapsuleMarketplace | — | See `deployments/base.json` |

All deployment records are stored in `contracts/deployments/` JSON files.
