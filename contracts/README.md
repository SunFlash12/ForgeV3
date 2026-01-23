# Forge CapsuleMarketplace Smart Contracts

Smart contracts for the Forge Capsule Marketplace on Base L2.

## Overview

The `CapsuleMarketplace` contract enables buying and selling knowledge capsules using $VIRTUAL tokens on Base. It automatically handles payment distribution:

| Recipient | Share |
|-----------|-------|
| Seller (Capsule Author) | 70% |
| Lineage (Ancestors) | 15% |
| Platform Treasury | 10% |
| DAO Treasury | 5% |

## Setup

```bash
# Install dependencies
npm install

# Copy environment file
cp .env.example .env
# Edit .env with your values
```

## Configuration

Edit `.env` with:
- `DEPLOYER_PRIVATE_KEY`: Wallet private key for deployment
- `PLATFORM_TREASURY_ADDRESS`: Your platform treasury (frowg.base.eth resolved)
- `DAO_TREASURY_ADDRESS`: DAO treasury address
- `BASESCAN_API_KEY`: For contract verification

## Commands

```bash
# Compile contracts
npm run compile

# Run tests
npm test

# Run tests with coverage
npm run test:coverage

# Deploy to Base Sepolia (testnet)
npm run deploy:base-sepolia

# Deploy to Base (mainnet)
npm run deploy:base

# Verify contract on Basescan
npm run verify:base -- <CONTRACT_ADDRESS> "<VIRTUAL_TOKEN>" "<PLATFORM_TREASURY>" "<DAO_TREASURY>"
```

## Contract Addresses

### $VIRTUAL Token
- Base Mainnet: `0x0b3e328455c4059EEb9e3f84b5543F74E24e7E1b`
- Base Sepolia: `0x0b3e328455c4059EEb9e3f84b5543F74E24e7E1b`

### CapsuleMarketplace
- Base Mainnet: `TBD`
- Base Sepolia: `TBD`

## Usage

### Creating a Listing

```solidity
// Seller creates a listing
marketplace.createListing(
    capsuleId,      // bytes32 - unique capsule ID
    priceInVirtual, // uint256 - price in $VIRTUAL (18 decimals)
    lineageAddresses // address[] - ancestor capsule owners
);
```

### Purchasing a Capsule

```solidity
// Buyer approves tokens first
virtualToken.approve(marketplaceAddress, amount);

// Then purchases
marketplace.purchaseCapsule(capsuleId);
```

### Verifying a Purchase

```solidity
// Backend verifies purchase
bool valid = marketplace.verifyPurchase(capsuleId, buyerAddress, txId);
```

## Security

- ReentrancyGuard for all purchase functions
- Pausable for emergency stops
- SafeERC20 for token transfers
- Owner-controlled admin functions

## License

MIT
