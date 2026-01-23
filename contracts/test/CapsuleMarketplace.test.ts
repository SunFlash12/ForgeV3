import { expect } from "chai";
import { ethers } from "hardhat";
import { CapsuleMarketplace, MockERC20 } from "../typechain-types";
import { SignerWithAddress } from "@nomicfoundation/hardhat-ethers/signers";

describe("CapsuleMarketplace", function () {
  let marketplace: CapsuleMarketplace;
  let virtualToken: MockERC20;
  let owner: SignerWithAddress;
  let seller: SignerWithAddress;
  let buyer: SignerWithAddress;
  let lineage1: SignerWithAddress;
  let lineage2: SignerWithAddress;
  let platformTreasury: SignerWithAddress;
  let daoTreasury: SignerWithAddress;

  const CAPSULE_ID = ethers.id("test-capsule-001");
  const PRICE = ethers.parseEther("100"); // 100 $VIRTUAL

  beforeEach(async function () {
    [owner, seller, buyer, lineage1, lineage2, platformTreasury, daoTreasury] =
      await ethers.getSigners();

    // Deploy mock token
    const MockToken = await ethers.getContractFactory("MockERC20");
    virtualToken = await MockToken.deploy("Virtual Token", "VIRTUAL", 18);

    // Deploy marketplace
    const Marketplace = await ethers.getContractFactory("CapsuleMarketplace");
    marketplace = await Marketplace.deploy(
      await virtualToken.getAddress(),
      platformTreasury.address,
      daoTreasury.address
    );

    // Mint tokens to buyer
    await virtualToken.mint(buyer.address, ethers.parseEther("10000"));
  });

  describe("Deployment", function () {
    it("Should set the correct token address", async function () {
      expect(await marketplace.virtualToken()).to.equal(
        await virtualToken.getAddress()
      );
    });

    it("Should set the correct treasury addresses", async function () {
      expect(await marketplace.platformTreasury()).to.equal(
        platformTreasury.address
      );
      expect(await marketplace.daoTreasury()).to.equal(daoTreasury.address);
    });

    it("Should set the correct shares", async function () {
      expect(await marketplace.SELLER_SHARE()).to.equal(7000);
      expect(await marketplace.LINEAGE_SHARE()).to.equal(1500);
      expect(await marketplace.PLATFORM_SHARE()).to.equal(1000);
      expect(await marketplace.DAO_SHARE()).to.equal(500);
    });
  });

  describe("Listings", function () {
    it("Should create a listing", async function () {
      await marketplace
        .connect(seller)
        .createListing(CAPSULE_ID, PRICE, [lineage1.address, lineage2.address]);

      const listing = await marketplace.getListing(CAPSULE_ID);
      expect(listing.seller).to.equal(seller.address);
      expect(listing.priceInVirtual).to.equal(PRICE);
      expect(listing.active).to.be.true;
    });

    it("Should emit ListingCreated event", async function () {
      await expect(
        marketplace.connect(seller).createListing(CAPSULE_ID, PRICE, [])
      )
        .to.emit(marketplace, "ListingCreated")
        .withArgs(CAPSULE_ID, seller.address, PRICE);
    });

    it("Should reject duplicate listings", async function () {
      await marketplace.connect(seller).createListing(CAPSULE_ID, PRICE, []);
      await expect(
        marketplace.connect(seller).createListing(CAPSULE_ID, PRICE, [])
      ).to.be.revertedWithCustomError(marketplace, "ListingAlreadyExists");
    });

    it("Should reject zero price", async function () {
      await expect(
        marketplace.connect(seller).createListing(CAPSULE_ID, 0, [])
      ).to.be.revertedWithCustomError(marketplace, "InvalidPrice");
    });
  });

  describe("Purchases", function () {
    beforeEach(async function () {
      // Create listing with lineage
      await marketplace
        .connect(seller)
        .createListing(CAPSULE_ID, PRICE, [lineage1.address, lineage2.address]);

      // Approve tokens
      await virtualToken
        .connect(buyer)
        .approve(await marketplace.getAddress(), PRICE);
    });

    it("Should complete a purchase with correct distribution", async function () {
      const sellerBefore = await virtualToken.balanceOf(seller.address);
      const lineage1Before = await virtualToken.balanceOf(lineage1.address);
      const lineage2Before = await virtualToken.balanceOf(lineage2.address);
      const platformBefore = await virtualToken.balanceOf(
        platformTreasury.address
      );
      const daoBefore = await virtualToken.balanceOf(daoTreasury.address);

      await marketplace.connect(buyer).purchaseCapsule(CAPSULE_ID);

      const sellerAfter = await virtualToken.balanceOf(seller.address);
      const lineage1After = await virtualToken.balanceOf(lineage1.address);
      const lineage2After = await virtualToken.balanceOf(lineage2.address);
      const platformAfter = await virtualToken.balanceOf(
        platformTreasury.address
      );
      const daoAfter = await virtualToken.balanceOf(daoTreasury.address);

      // Seller gets 70%
      expect(sellerAfter - sellerBefore).to.equal(ethers.parseEther("70"));

      // Lineage split 15% (7.5 each)
      expect(lineage1After - lineage1Before).to.equal(ethers.parseEther("7.5"));
      expect(lineage2After - lineage2Before).to.equal(ethers.parseEther("7.5"));

      // Platform gets 10%
      expect(platformAfter - platformBefore).to.equal(ethers.parseEther("10"));

      // DAO gets 5%
      expect(daoAfter - daoBefore).to.equal(ethers.parseEther("5"));
    });

    it("Should emit CapsulePurchased event", async function () {
      await expect(marketplace.connect(buyer).purchaseCapsule(CAPSULE_ID))
        .to.emit(marketplace, "CapsulePurchased")
        .withArgs(
          CAPSULE_ID,
          buyer.address,
          seller.address,
          PRICE,
          ethers.parseEther("70"), // seller
          ethers.parseEther("15"), // lineage
          ethers.parseEther("10"), // platform
          ethers.parseEther("5") // dao
        );
    });

    it("Should update stats after purchase", async function () {
      await marketplace.connect(buyer).purchaseCapsule(CAPSULE_ID);

      expect(await marketplace.totalVolume()).to.equal(PRICE);
      expect(await marketplace.totalPurchases()).to.equal(1);

      const listing = await marketplace.getListing(CAPSULE_ID);
      expect(listing.salesCount).to.equal(1);
    });

    it("Should reject purchase without approval", async function () {
      await virtualToken
        .connect(buyer)
        .approve(await marketplace.getAddress(), 0);
      await expect(
        marketplace.connect(buyer).purchaseCapsule(CAPSULE_ID)
      ).to.be.revertedWithCustomError(marketplace, "InsufficientAllowance");
    });

    it("Should reject purchase of inactive listing", async function () {
      await marketplace.connect(seller).toggleListing(CAPSULE_ID);
      await expect(
        marketplace.connect(buyer).purchaseCapsule(CAPSULE_ID)
      ).to.be.revertedWithCustomError(marketplace, "ListingNotActive");
    });
  });

  describe("Purchase without lineage", function () {
    beforeEach(async function () {
      // Create listing WITHOUT lineage
      await marketplace.connect(seller).createListing(CAPSULE_ID, PRICE, []);
      await virtualToken
        .connect(buyer)
        .approve(await marketplace.getAddress(), PRICE);
    });

    it("Should give lineage share to platform when no lineage", async function () {
      const platformBefore = await virtualToken.balanceOf(
        platformTreasury.address
      );

      await marketplace.connect(buyer).purchaseCapsule(CAPSULE_ID);

      const platformAfter = await virtualToken.balanceOf(
        platformTreasury.address
      );

      // Platform gets 10% + 15% = 25%
      expect(platformAfter - platformBefore).to.equal(ethers.parseEther("25"));
    });
  });

  describe("Admin functions", function () {
    it("Should allow owner to pause/unpause", async function () {
      await marketplace.connect(owner).pause();
      expect(await marketplace.paused()).to.be.true;

      await marketplace.connect(owner).unpause();
      expect(await marketplace.paused()).to.be.false;
    });

    it("Should allow owner to update treasury", async function () {
      const newTreasury = buyer.address;
      await marketplace.connect(owner).setPlatformTreasury(newTreasury);
      expect(await marketplace.platformTreasury()).to.equal(newTreasury);
    });

    it("Should reject non-owner admin calls", async function () {
      await expect(
        marketplace.connect(seller).pause()
      ).to.be.revertedWithCustomError(marketplace, "OwnableUnauthorizedAccount");
    });
  });

  describe("Purchase verification", function () {
    it("Should verify valid purchase", async function () {
      await marketplace
        .connect(seller)
        .createListing(CAPSULE_ID, PRICE, []);
      await virtualToken
        .connect(buyer)
        .approve(await marketplace.getAddress(), PRICE);

      await marketplace.connect(buyer).purchaseCapsule(CAPSULE_ID);

      const purchases = await marketplace.getPurchaseHistory(CAPSULE_ID);
      expect(purchases.length).to.equal(1);
      expect(purchases[0].buyer).to.equal(buyer.address);

      const isValid = await marketplace.verifyPurchase(
        CAPSULE_ID,
        buyer.address,
        purchases[0].txId
      );
      expect(isValid).to.be.true;
    });
  });
});
