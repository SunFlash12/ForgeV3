import { ethers, network, run } from "hardhat";
import * as fs from "fs";
import * as path from "path";

// Contract addresses
const ADDRESSES = {
  // $VIRTUAL Token on Base
  VIRTUAL_TOKEN: {
    base: "0x0b3e328455c4059EEb9e3f84b5543F74E24e7E1b",
    baseSepolia: "0x0b3e328455c4059EEb9e3f84b5543F74E24e7E1b", // Same address
  },
  // Platform Treasury - frowg.base.eth
  // Note: ENS names need to be resolved. Using placeholder until resolved.
  PLATFORM_TREASURY: {
    base: process.env.PLATFORM_TREASURY_ADDRESS || "",
    baseSepolia: process.env.PLATFORM_TREASURY_ADDRESS || "",
  },
  // DAO Treasury
  DAO_TREASURY: {
    base: process.env.DAO_TREASURY_ADDRESS || "",
    baseSepolia: process.env.DAO_TREASURY_ADDRESS || "",
  },
};

async function main() {
  const networkName = network.name as "base" | "baseSepolia" | "hardhat" | "localhost";

  console.log("============================================");
  console.log("Forge CapsuleMarketplace Deployment");
  console.log("============================================");
  console.log(`Network: ${networkName}`);
  console.log(`Chain ID: ${network.config.chainId}`);

  const [deployer] = await ethers.getSigners();
  console.log(`Deployer: ${deployer.address}`);

  const balance = await ethers.provider.getBalance(deployer.address);
  console.log(`Balance: ${ethers.formatEther(balance)} ETH`);
  console.log("--------------------------------------------");

  // Get addresses for current network
  let virtualToken: string;
  let platformTreasury: string;
  let daoTreasury: string;

  if (networkName === "hardhat" || networkName === "localhost") {
    // For local testing, deploy a mock token
    console.log("Deploying mock $VIRTUAL token for testing...");
    const MockToken = await ethers.getContractFactory("MockERC20");
    const mockToken = await MockToken.deploy("Virtual Token", "VIRTUAL", 18);
    await mockToken.waitForDeployment();
    virtualToken = await mockToken.getAddress();
    console.log(`Mock $VIRTUAL deployed: ${virtualToken}`);

    // Use deployer as treasuries for testing
    platformTreasury = deployer.address;
    daoTreasury = deployer.address;
  } else {
    virtualToken = ADDRESSES.VIRTUAL_TOKEN[networkName === "baseSepolia" ? "baseSepolia" : "base"];
    platformTreasury = ADDRESSES.PLATFORM_TREASURY[networkName === "baseSepolia" ? "baseSepolia" : "base"];
    daoTreasury = ADDRESSES.DAO_TREASURY[networkName === "baseSepolia" ? "baseSepolia" : "base"];

    // Validate addresses
    if (!platformTreasury) {
      throw new Error("PLATFORM_TREASURY_ADDRESS not set in environment");
    }
    if (!daoTreasury) {
      throw new Error("DAO_TREASURY_ADDRESS not set in environment");
    }
  }

  console.log("\nDeployment Parameters:");
  console.log(`  $VIRTUAL Token: ${virtualToken}`);
  console.log(`  Platform Treasury: ${platformTreasury}`);
  console.log(`  DAO Treasury: ${daoTreasury}`);
  console.log("--------------------------------------------");

  // Deploy CapsuleMarketplace
  console.log("\nDeploying CapsuleMarketplace...");
  const CapsuleMarketplace = await ethers.getContractFactory("CapsuleMarketplace");
  const marketplace = await CapsuleMarketplace.deploy(
    virtualToken,
    platformTreasury,
    daoTreasury
  );

  await marketplace.waitForDeployment();
  const marketplaceAddress = await marketplace.getAddress();

  console.log(`CapsuleMarketplace deployed: ${marketplaceAddress}`);
  console.log(`Transaction hash: ${marketplace.deploymentTransaction()?.hash}`);

  // Wait for confirmations
  if (networkName !== "hardhat" && networkName !== "localhost") {
    console.log("\nWaiting for confirmations...");
    await marketplace.deploymentTransaction()?.wait(5);
    console.log("Confirmed!");
  }

  // Save deployment info
  const deploymentInfo = {
    network: networkName,
    chainId: network.config.chainId,
    contracts: {
      CapsuleMarketplace: {
        address: marketplaceAddress,
        deploymentTx: marketplace.deploymentTransaction()?.hash,
      },
    },
    parameters: {
      virtualToken,
      platformTreasury,
      daoTreasury,
    },
    timestamp: new Date().toISOString(),
  };

  const deploymentsDir = path.join(__dirname, "../deployments");
  if (!fs.existsSync(deploymentsDir)) {
    fs.mkdirSync(deploymentsDir, { recursive: true });
  }

  const deploymentFile = path.join(deploymentsDir, `${networkName}.json`);
  fs.writeFileSync(deploymentFile, JSON.stringify(deploymentInfo, null, 2));
  console.log(`\nDeployment info saved to: ${deploymentFile}`);

  // Verify on Basescan (if not local)
  if (networkName === "base" || networkName === "baseSepolia") {
    console.log("\n--------------------------------------------");
    console.log("Verifying contract on Basescan...");

    try {
      await run("verify:verify", {
        address: marketplaceAddress,
        constructorArguments: [virtualToken, platformTreasury, daoTreasury],
      });
      console.log("Contract verified successfully!");
    } catch (error: any) {
      if (error.message.includes("Already Verified")) {
        console.log("Contract is already verified!");
      } else {
        console.error("Verification failed:", error.message);
        console.log("\nTo verify manually, run:");
        console.log(`npx hardhat verify --network ${networkName} ${marketplaceAddress} "${virtualToken}" "${platformTreasury}" "${daoTreasury}"`);
      }
    }
  }

  console.log("\n============================================");
  console.log("Deployment Complete!");
  console.log("============================================");
  console.log(`\nCapsuleMarketplace: ${marketplaceAddress}`);
  console.log(`\nView on Basescan: https://${networkName === "baseSepolia" ? "sepolia." : ""}basescan.org/address/${marketplaceAddress}`);

  return deploymentInfo;
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
