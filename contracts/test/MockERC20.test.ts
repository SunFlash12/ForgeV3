import { expect } from "chai";
import { ethers } from "hardhat";
import { MockERC20 } from "../typechain-types";
import { SignerWithAddress } from "@nomicfoundation/hardhat-ethers/signers";

describe("MockERC20", function () {
  let token: MockERC20;
  let owner: SignerWithAddress;
  let alice: SignerWithAddress;
  let bob: SignerWithAddress;

  const NAME = "Test Token";
  const SYMBOL = "TST";
  const DECIMALS = 18;

  beforeEach(async function () {
    [owner, alice, bob] = await ethers.getSigners();

    const MockToken = await ethers.getContractFactory("MockERC20");
    token = await MockToken.deploy(NAME, SYMBOL, DECIMALS);
  });

  // ---------------------------------------------------------------------------
  // 1. Deployment
  // ---------------------------------------------------------------------------
  describe("Deployment", function () {
    it("Should set the correct name", async function () {
      expect(await token.name()).to.equal(NAME);
    });

    it("Should set the correct symbol", async function () {
      expect(await token.symbol()).to.equal(SYMBOL);
    });

    it("Should set the correct decimals", async function () {
      expect(await token.decimals()).to.equal(DECIMALS);
    });

    it("Should start with zero totalSupply", async function () {
      expect(await token.totalSupply()).to.equal(0);
    });

    it("Should start with zero balance for all accounts", async function () {
      expect(await token.balanceOf(owner.address)).to.equal(0);
      expect(await token.balanceOf(alice.address)).to.equal(0);
      expect(await token.balanceOf(bob.address)).to.equal(0);
    });
  });

  // ---------------------------------------------------------------------------
  // 2. mint
  // ---------------------------------------------------------------------------
  describe("mint", function () {
    const MINT_AMOUNT = ethers.parseEther("1000");

    it("Should increase the balance of the recipient", async function () {
      await token.mint(alice.address, MINT_AMOUNT);
      expect(await token.balanceOf(alice.address)).to.equal(MINT_AMOUNT);
    });

    it("Should increase totalSupply", async function () {
      await token.mint(alice.address, MINT_AMOUNT);
      expect(await token.totalSupply()).to.equal(MINT_AMOUNT);
    });

    it("Should allow multiple mints to accumulate", async function () {
      await token.mint(alice.address, MINT_AMOUNT);
      await token.mint(alice.address, MINT_AMOUNT);
      expect(await token.balanceOf(alice.address)).to.equal(MINT_AMOUNT * 2n);
      expect(await token.totalSupply()).to.equal(MINT_AMOUNT * 2n);
    });

    it("Should allow anyone to call mint (not restricted)", async function () {
      // owner mints
      await token.connect(owner).mint(alice.address, MINT_AMOUNT);
      // alice mints (non-owner)
      await token.connect(alice).mint(bob.address, MINT_AMOUNT);
      // bob mints to self
      await token.connect(bob).mint(bob.address, MINT_AMOUNT);

      expect(await token.balanceOf(alice.address)).to.equal(MINT_AMOUNT);
      expect(await token.balanceOf(bob.address)).to.equal(MINT_AMOUNT * 2n);
      expect(await token.totalSupply()).to.equal(MINT_AMOUNT * 3n);
    });

    it("Should emit Transfer event from zero address", async function () {
      await expect(token.mint(alice.address, MINT_AMOUNT))
        .to.emit(token, "Transfer")
        .withArgs(ethers.ZeroAddress, alice.address, MINT_AMOUNT);
    });

    it("Should handle minting zero tokens", async function () {
      await token.mint(alice.address, 0);
      expect(await token.balanceOf(alice.address)).to.equal(0);
      expect(await token.totalSupply()).to.equal(0);
    });
  });

  // ---------------------------------------------------------------------------
  // 3. burn
  // ---------------------------------------------------------------------------
  describe("burn", function () {
    const MINT_AMOUNT = ethers.parseEther("1000");
    const BURN_AMOUNT = ethers.parseEther("400");

    beforeEach(async function () {
      await token.mint(alice.address, MINT_AMOUNT);
    });

    it("Should decrease the balance of the target", async function () {
      await token.burn(alice.address, BURN_AMOUNT);
      expect(await token.balanceOf(alice.address)).to.equal(
        MINT_AMOUNT - BURN_AMOUNT
      );
    });

    it("Should decrease totalSupply", async function () {
      await token.burn(alice.address, BURN_AMOUNT);
      expect(await token.totalSupply()).to.equal(MINT_AMOUNT - BURN_AMOUNT);
    });

    it("Should allow burning the entire balance", async function () {
      await token.burn(alice.address, MINT_AMOUNT);
      expect(await token.balanceOf(alice.address)).to.equal(0);
      expect(await token.totalSupply()).to.equal(0);
    });

    it("Should revert if burn amount exceeds balance", async function () {
      const tooMuch = MINT_AMOUNT + 1n;
      await expect(token.burn(alice.address, tooMuch)).to.be.revertedWithCustomError(
        token,
        "ERC20InsufficientBalance"
      );
    });

    it("Should allow anyone to call burn (not restricted)", async function () {
      // bob (non-owner, non-holder) burns from alice
      await token.connect(bob).burn(alice.address, BURN_AMOUNT);
      expect(await token.balanceOf(alice.address)).to.equal(
        MINT_AMOUNT - BURN_AMOUNT
      );
    });

    it("Should emit Transfer event to zero address", async function () {
      await expect(token.burn(alice.address, BURN_AMOUNT))
        .to.emit(token, "Transfer")
        .withArgs(alice.address, ethers.ZeroAddress, BURN_AMOUNT);
    });

    it("Should handle burning zero tokens", async function () {
      await token.burn(alice.address, 0);
      expect(await token.balanceOf(alice.address)).to.equal(MINT_AMOUNT);
    });
  });

  // ---------------------------------------------------------------------------
  // 4. decimals (custom values)
  // ---------------------------------------------------------------------------
  describe("decimals", function () {
    it("Should support 8 decimals", async function () {
      const Factory = await ethers.getContractFactory("MockERC20");
      const token8 = await Factory.deploy("Eight Dec", "DEC8", 8);
      expect(await token8.decimals()).to.equal(8);
    });

    it("Should support 18 decimals", async function () {
      const Factory = await ethers.getContractFactory("MockERC20");
      const token18 = await Factory.deploy("Eighteen Dec", "DEC18", 18);
      expect(await token18.decimals()).to.equal(18);
    });

    it("Should support 0 decimals", async function () {
      const Factory = await ethers.getContractFactory("MockERC20");
      const token0 = await Factory.deploy("Zero Dec", "DEC0", 0);
      expect(await token0.decimals()).to.equal(0);
    });

    it("Should support maximum uint8 decimals (255)", async function () {
      const Factory = await ethers.getContractFactory("MockERC20");
      const tokenMax = await Factory.deploy("Max Dec", "DMAX", 255);
      expect(await tokenMax.decimals()).to.equal(255);
    });

    it("Should use custom decimals independently from minting", async function () {
      const Factory = await ethers.getContractFactory("MockERC20");
      const token8 = await Factory.deploy("USDC Mock", "mUSDC", 6);

      const amount = 1_000_000n; // 1 token with 6 decimals
      await token8.mint(alice.address, amount);

      expect(await token8.decimals()).to.equal(6);
      expect(await token8.balanceOf(alice.address)).to.equal(amount);
    });
  });

  // ---------------------------------------------------------------------------
  // 5. ERC20 basics (inherited from OpenZeppelin)
  // ---------------------------------------------------------------------------
  describe("ERC20 basics", function () {
    const INITIAL = ethers.parseEther("1000");

    beforeEach(async function () {
      await token.mint(alice.address, INITIAL);
    });

    // -- transfer --

    describe("transfer", function () {
      it("Should transfer tokens between accounts", async function () {
        const amount = ethers.parseEther("200");
        await token.connect(alice).transfer(bob.address, amount);

        expect(await token.balanceOf(alice.address)).to.equal(INITIAL - amount);
        expect(await token.balanceOf(bob.address)).to.equal(amount);
      });

      it("Should emit Transfer event", async function () {
        const amount = ethers.parseEther("200");
        await expect(token.connect(alice).transfer(bob.address, amount))
          .to.emit(token, "Transfer")
          .withArgs(alice.address, bob.address, amount);
      });

      it("Should revert when sender has insufficient balance", async function () {
        const tooMuch = INITIAL + 1n;
        await expect(
          token.connect(alice).transfer(bob.address, tooMuch)
        ).to.be.revertedWithCustomError(token, "ERC20InsufficientBalance");
      });

      it("Should not change totalSupply", async function () {
        const amount = ethers.parseEther("200");
        await token.connect(alice).transfer(bob.address, amount);
        expect(await token.totalSupply()).to.equal(INITIAL);
      });
    });

    // -- approve + transferFrom --

    describe("approve and transferFrom", function () {
      const ALLOWANCE = ethers.parseEther("500");

      it("Should set allowance via approve", async function () {
        await token.connect(alice).approve(bob.address, ALLOWANCE);
        expect(await token.allowance(alice.address, bob.address)).to.equal(
          ALLOWANCE
        );
      });

      it("Should emit Approval event", async function () {
        await expect(token.connect(alice).approve(bob.address, ALLOWANCE))
          .to.emit(token, "Approval")
          .withArgs(alice.address, bob.address, ALLOWANCE);
      });

      it("Should allow transferFrom within allowance", async function () {
        const transferAmount = ethers.parseEther("300");
        await token.connect(alice).approve(bob.address, ALLOWANCE);
        await token
          .connect(bob)
          .transferFrom(alice.address, bob.address, transferAmount);

        expect(await token.balanceOf(alice.address)).to.equal(
          INITIAL - transferAmount
        );
        expect(await token.balanceOf(bob.address)).to.equal(transferAmount);
      });

      it("Should decrease allowance after transferFrom", async function () {
        const transferAmount = ethers.parseEther("300");
        await token.connect(alice).approve(bob.address, ALLOWANCE);
        await token
          .connect(bob)
          .transferFrom(alice.address, bob.address, transferAmount);

        expect(await token.allowance(alice.address, bob.address)).to.equal(
          ALLOWANCE - transferAmount
        );
      });

      it("Should revert transferFrom exceeding allowance", async function () {
        const tooMuch = ALLOWANCE + 1n;
        await token.connect(alice).approve(bob.address, ALLOWANCE);
        await expect(
          token.connect(bob).transferFrom(alice.address, bob.address, tooMuch)
        ).to.be.revertedWithCustomError(token, "ERC20InsufficientAllowance");
      });

      it("Should revert transferFrom exceeding balance even with allowance", async function () {
        const overBalance = INITIAL + 1n;
        await token.connect(alice).approve(bob.address, overBalance);
        await expect(
          token
            .connect(bob)
            .transferFrom(alice.address, bob.address, overBalance)
        ).to.be.revertedWithCustomError(token, "ERC20InsufficientBalance");
      });

      it("Should allow unlimited allowance (MaxUint256)", async function () {
        await token.connect(alice).approve(bob.address, ethers.MaxUint256);

        const transferAmount = ethers.parseEther("100");
        await token
          .connect(bob)
          .transferFrom(alice.address, bob.address, transferAmount);

        // OZ ERC20: unlimited allowance does not decrease
        expect(await token.allowance(alice.address, bob.address)).to.equal(
          ethers.MaxUint256
        );
      });

      it("Should update allowance on repeated approve calls", async function () {
        await token.connect(alice).approve(bob.address, ALLOWANCE);
        const newAllowance = ethers.parseEther("100");
        await token.connect(alice).approve(bob.address, newAllowance);
        expect(await token.allowance(alice.address, bob.address)).to.equal(
          newAllowance
        );
      });
    });
  });
});
