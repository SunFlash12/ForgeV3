/**
 * Resolve ENS/Basename addresses
 *
 * Usage: npx ts-node scripts/resolve-ens.ts frowg.base.eth
 */

import { ethers } from "ethers";

async function resolveENS(name: string) {
  // Use Base mainnet RPC
  const provider = new ethers.JsonRpcProvider("https://mainnet.base.org");

  console.log(`Resolving: ${name}`);

  try {
    // For .base.eth names, we need to use the Base Name Service
    // The resolver is at a specific address on Base
    const address = await provider.resolveName(name);

    if (address) {
      console.log(`✅ Resolved: ${name} => ${address}`);
      return address;
    } else {
      console.log(`❌ Could not resolve: ${name}`);

      // Try alternative resolution methods
      console.log("\nAttempting alternative resolution...");

      // Base Name Service Registry
      const BNS_REGISTRY = "0x4cCb0BB02FCABA27e82a56646E81d8c5bC4119a5";

      // Normalize the name
      const normalizedName = name.toLowerCase();
      const nameHash = ethers.namehash(normalizedName);

      console.log(`Name hash: ${nameHash}`);

      return null;
    }
  } catch (error: any) {
    console.error(`Error resolving ${name}:`, error.message);
    return null;
  }
}

async function main() {
  const args = process.argv.slice(2);

  if (args.length === 0) {
    // Default: resolve the platform treasury address
    await resolveENS("frowg.base.eth");
  } else {
    for (const name of args) {
      await resolveENS(name);
      console.log();
    }
  }
}

main().catch(console.error);
