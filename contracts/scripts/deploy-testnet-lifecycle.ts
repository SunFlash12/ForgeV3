import { ethers, network, run } from "hardhat";
import * as fs from "fs";
import * as path from "path";

/**
 * Deploy the full testnet lifecycle contracts to Base Sepolia:
 *   1. CapsuleRegistry  — on-chain capsule hash anchoring
 *   2. SimpleEscrow      — ETH-based ACP job escrow
 *   3. MockERC20 x3      — tVIRTUAL, GOT (Genomic Ontology Token), VCT (Variant Classifier Token)
 *   4. Mint 10,000 tVIRTUAL to operator
 *
 * Usage:
 *   cd contracts
 *   npx hardhat run scripts/deploy-testnet-lifecycle.ts --network baseSepolia
 */

const TOKEN_CONFIGS = [
  { name: "Test VIRTUAL", symbol: "tVIRTUAL", decimals: 18, mintAmount: 10000 },
  { name: "Genomic Ontology Token", symbol: "GOT", decimals: 18, mintAmount: 1000 },
  { name: "Variant Classifier Token", symbol: "VCT", decimals: 18, mintAmount: 1000 },
];

async function main() {
  const networkName = network.name;
  const chainId = network.config.chainId;

  console.log("════════════════════════════════════════════════════════");
  console.log("  Forge Testnet Lifecycle — Contract Deployment");
  console.log("════════════════════════════════════════════════════════");
  console.log(`Network:  ${networkName}`);
  console.log(`Chain ID: ${chainId}`);

  // Safety: only allow baseSepolia or local networks
  if (networkName !== "baseSepolia" && networkName !== "hardhat" && networkName !== "localhost") {
    throw new Error(`Safety guard: refusing to deploy to ${networkName}. Only baseSepolia/hardhat/localhost allowed.`);
  }

  const [deployer] = await ethers.getSigners();
  console.log(`Deployer: ${deployer.address}`);

  const balance = await ethers.provider.getBalance(deployer.address);
  console.log(`Balance:  ${ethers.formatEther(balance)} ETH`);
  console.log("────────────────────────────────────────────────────────");

  const deployedContracts: Record<string, { address: string; tx?: string }> = {};
  const tokenAddresses: Record<string, string> = {};

  // Helper: wait for tx confirmation + small delay to avoid nonce race conditions
  const waitForConfirmation = async (contract: any, label: string) => {
    const tx = contract.deploymentTransaction();
    if (tx) {
      console.log(`  Waiting for ${label} confirmation...`);
      await tx.wait(1); // Wait for 1 block confirmation
      // Small delay to let RPC state propagate
      await new Promise((resolve) => setTimeout(resolve, 3000));
    }
  };

  // ═══════════════════════════════════════════════════════════════════════
  // 1. Deploy CapsuleRegistry
  // ═══════════════════════════════════════════════════════════════════════
  console.log("\n[1/5] Deploying CapsuleRegistry...");
  const CapsuleRegistry = await ethers.getContractFactory("CapsuleRegistry");
  const registry = await CapsuleRegistry.deploy();
  await registry.waitForDeployment();
  const registryAddress = await registry.getAddress();
  const registryTx = registry.deploymentTransaction()?.hash;
  console.log(`  Address: ${registryAddress}`);
  console.log(`  Tx:      ${registryTx}`);
  deployedContracts["CapsuleRegistry"] = { address: registryAddress, tx: registryTx };
  await waitForConfirmation(registry, "CapsuleRegistry");

  // ═══════════════════════════════════════════════════════════════════════
  // 2. Deploy SimpleEscrow
  // ═══════════════════════════════════════════════════════════════════════
  console.log("\n[2/5] Deploying SimpleEscrow...");
  const maxEscrowAmount = ethers.parseEther("0.01"); // Configurable — owner can change post-deploy
  console.log(`  Max escrow amount: ${ethers.formatEther(maxEscrowAmount)} ETH`);
  const SimpleEscrow = await ethers.getContractFactory("SimpleEscrow");
  const escrow = await SimpleEscrow.deploy(maxEscrowAmount);
  await escrow.waitForDeployment();
  const escrowAddress = await escrow.getAddress();
  const escrowTx = escrow.deploymentTransaction()?.hash;
  console.log(`  Address: ${escrowAddress}`);
  console.log(`  Tx:      ${escrowTx}`);
  deployedContracts["SimpleEscrow"] = { address: escrowAddress, tx: escrowTx };
  await waitForConfirmation(escrow, "SimpleEscrow");

  // ═══════════════════════════════════════════════════════════════════════
  // 3. Deploy MockERC20 tokens (tVIRTUAL, GOT, VCT)
  // ═══════════════════════════════════════════════════════════════════════
  for (let i = 0; i < TOKEN_CONFIGS.length; i++) {
    const cfg = TOKEN_CONFIGS[i];
    const step = i + 3;
    console.log(`\n[${step}/5] Deploying MockERC20: ${cfg.name} (${cfg.symbol})...`);

    const MockERC20 = await ethers.getContractFactory("MockERC20");
    const token = await MockERC20.deploy(cfg.name, cfg.symbol, cfg.decimals);
    await token.waitForDeployment();
    const tokenAddress = await token.getAddress();
    const tokenTx = token.deploymentTransaction()?.hash;
    console.log(`  Address: ${tokenAddress}`);
    console.log(`  Tx:      ${tokenTx}`);
    await waitForConfirmation(token, cfg.symbol);

    deployedContracts[cfg.symbol] = { address: tokenAddress, tx: tokenTx };
    tokenAddresses[cfg.symbol] = tokenAddress;

    // Mint tokens to deployer
    const mintAmount = ethers.parseUnits(cfg.mintAmount.toString(), cfg.decimals);
    console.log(`  Minting ${cfg.mintAmount} ${cfg.symbol} to ${deployer.address}...`);
    const mintTx = await token.mint(deployer.address, mintAmount);
    await mintTx.wait(1);
    console.log(`  Mint tx: ${mintTx.hash}`);
    deployedContracts[`${cfg.symbol}_mint`] = { address: tokenAddress, tx: mintTx.hash };
    // Delay between token deployments to avoid nonce race conditions
    await new Promise((resolve) => setTimeout(resolve, 3000));
  }

  // ═══════════════════════════════════════════════════════════════════════
  // Wait for confirmations on real networks
  // ═══════════════════════════════════════════════════════════════════════
  if (networkName !== "hardhat" && networkName !== "localhost") {
    console.log("\nWaiting for block confirmations...");
    // Wait for the last deployment tx
    await registry.deploymentTransaction()?.wait(3);
    await escrow.deploymentTransaction()?.wait(3);
    console.log("All contracts confirmed on-chain.");
  }

  // ═══════════════════════════════════════════════════════════════════════
  // Save deployment info
  // ═══════════════════════════════════════════════════════════════════════
  const deploymentInfo = {
    network: networkName,
    chainId: chainId,
    deployer: deployer.address,
    contracts: {
      CapsuleRegistry: {
        address: registryAddress,
        deploymentTx: registryTx,
      },
      SimpleEscrow: {
        address: escrowAddress,
        deploymentTx: escrowTx,
      },
      tVIRTUAL: {
        address: tokenAddresses["tVIRTUAL"],
        deploymentTx: deployedContracts["tVIRTUAL"]?.tx,
        mintTx: deployedContracts["tVIRTUAL_mint"]?.tx,
      },
      GOT: {
        address: tokenAddresses["GOT"],
        deploymentTx: deployedContracts["GOT"]?.tx,
        mintTx: deployedContracts["GOT_mint"]?.tx,
      },
      VCT: {
        address: tokenAddresses["VCT"],
        deploymentTx: deployedContracts["VCT"]?.tx,
        mintTx: deployedContracts["VCT_mint"]?.tx,
      },
    },
    timestamp: new Date().toISOString(),
  };

  const deploymentsDir = path.join(__dirname, "../deployments");
  if (!fs.existsSync(deploymentsDir)) {
    fs.mkdirSync(deploymentsDir, { recursive: true });
  }

  const deploymentFile = path.join(deploymentsDir, "baseSepolia.json");
  fs.writeFileSync(deploymentFile, JSON.stringify(deploymentInfo, null, 2));
  console.log(`\nDeployment info saved to: deployments/baseSepolia.json`);

  // ═══════════════════════════════════════════════════════════════════════
  // Verify contracts (if BaseScan API key is available)
  // ═══════════════════════════════════════════════════════════════════════
  if (networkName === "baseSepolia") {
    console.log("\n────────────────────────────────────────────────────────");
    console.log("Verifying contracts on BaseScan...");

    const verifyConfigs = [
      { name: "CapsuleRegistry", address: registryAddress, args: [] },
      { name: "SimpleEscrow", address: escrowAddress, args: [maxEscrowAmount] },
      ...TOKEN_CONFIGS.map((cfg) => ({
        name: cfg.symbol,
        address: tokenAddresses[cfg.symbol],
        args: [cfg.name, cfg.symbol, cfg.decimals],
      })),
    ];

    for (const vc of verifyConfigs) {
      try {
        await run("verify:verify", {
          address: vc.address,
          constructorArguments: vc.args,
        });
        console.log(`  ✓ ${vc.name} verified`);
      } catch (error: any) {
        if (error.message?.includes("Already Verified")) {
          console.log(`  ✓ ${vc.name} already verified`);
        } else {
          console.log(`  ✗ ${vc.name} verification failed: ${error.message?.slice(0, 100)}`);
        }
      }
    }
  }

  // ═══════════════════════════════════════════════════════════════════════
  // Summary
  // ═══════════════════════════════════════════════════════════════════════
  const explorerBase = networkName === "baseSepolia"
    ? "https://sepolia.basescan.org"
    : "https://basescan.org";

  console.log("\n════════════════════════════════════════════════════════");
  console.log("  Deployment Complete!");
  console.log("════════════════════════════════════════════════════════");
  console.log(`\n  CapsuleRegistry: ${registryAddress}`);
  console.log(`  SimpleEscrow:    ${escrowAddress}`);
  console.log(`  tVIRTUAL:        ${tokenAddresses["tVIRTUAL"]}`);
  console.log(`  GOT:             ${tokenAddresses["GOT"]}`);
  console.log(`  VCT:             ${tokenAddresses["VCT"]}`);
  console.log(`\n  Explorer:`);
  console.log(`  ${explorerBase}/address/${registryAddress}`);
  console.log(`  ${explorerBase}/address/${escrowAddress}`);

  const finalBalance = await ethers.provider.getBalance(deployer.address);
  const gasUsed = balance - finalBalance;
  console.log(`\n  Gas used: ${ethers.formatEther(gasUsed)} ETH`);
  console.log(`  Remaining balance: ${ethers.formatEther(finalBalance)} ETH`);

  return deploymentInfo;
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
