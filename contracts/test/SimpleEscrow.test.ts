import { expect } from "chai";
import { ethers } from "hardhat";
import { SimpleEscrow, ReentrancyAttacker, ETHRejecter } from "../typechain-types";
import { SignerWithAddress } from "@nomicfoundation/hardhat-ethers/signers";
import { time } from "@nomicfoundation/hardhat-network-helpers";

describe("SimpleEscrow", function () {
  let escrow: SimpleEscrow;
  let owner: SignerWithAddress;
  let buyer: SignerWithAddress;
  let provider: SignerWithAddress;
  let stranger: SignerWithAddress;

  const MAX_ESCROW = ethers.parseEther("1"); // 1 ETH
  const ESCROW_AMOUNT = ethers.parseEther("0.5"); // 0.5 ETH
  const JOB_HASH = ethers.id("test-job-001");

  /** Helper: returns a deadline 1 hour in the future. */
  async function futureDeadline(): Promise<number> {
    const latest = await time.latest();
    return latest + 3600; // +1 hour
  }

  /** Helper: creates an escrow from `buyer` to `provider` with default params. */
  async function createDefaultEscrow(): Promise<bigint> {
    const deadline = await futureDeadline();
    const tx = await escrow
      .connect(buyer)
      .createEscrow(provider.address, deadline, JOB_HASH, {
        value: ESCROW_AMOUNT,
      });
    const receipt = await tx.wait();
    // escrowId is emitted as first indexed arg in EscrowCreated
    const event = receipt?.logs.find((log) => {
      try {
        return escrow.interface.parseLog({ topics: log.topics as string[], data: log.data })?.name === "EscrowCreated";
      } catch {
        return false;
      }
    });
    const parsed = escrow.interface.parseLog({
      topics: event!.topics as string[],
      data: event!.data,
    });
    return parsed!.args.escrowId;
  }

  beforeEach(async function () {
    [owner, buyer, provider, stranger] = await ethers.getSigners();

    const Factory = await ethers.getContractFactory("SimpleEscrow");
    escrow = await Factory.deploy(MAX_ESCROW);
  });

  // ═══════════════════════════════════════════════════════════════════════════
  // 1. Deployment
  // ═══════════════════════════════════════════════════════════════════════════

  describe("Deployment", function () {
    it("Should set deployer as owner", async function () {
      expect(await escrow.owner()).to.equal(owner.address);
    });

    it("Should set maxEscrowAmount from constructor arg", async function () {
      expect(await escrow.maxEscrowAmount()).to.equal(MAX_ESCROW);
    });

    it("Should initialise escrowCount to 0", async function () {
      expect(await escrow.escrowCount()).to.equal(0);
    });

    it("Should revert with InvalidMaxAmount when deployed with 0", async function () {
      const Factory = await ethers.getContractFactory("SimpleEscrow");
      await expect(Factory.deploy(0)).to.be.revertedWithCustomError(
        escrow,
        "InvalidMaxAmount"
      );
    });
  });

  // ═══════════════════════════════════════════════════════════════════════════
  // 2. setMaxEscrowAmount
  // ═══════════════════════════════════════════════════════════════════════════

  describe("setMaxEscrowAmount", function () {
    it("Should allow owner to update max amount", async function () {
      const newMax = ethers.parseEther("5");
      await escrow.connect(owner).setMaxEscrowAmount(newMax);
      expect(await escrow.maxEscrowAmount()).to.equal(newMax);
    });

    it("Should emit MaxEscrowAmountUpdated with old and new values", async function () {
      const newMax = ethers.parseEther("5");
      await expect(escrow.connect(owner).setMaxEscrowAmount(newMax))
        .to.emit(escrow, "MaxEscrowAmountUpdated")
        .withArgs(MAX_ESCROW, newMax);
    });

    it("Should revert when called by non-owner", async function () {
      await expect(
        escrow.connect(stranger).setMaxEscrowAmount(ethers.parseEther("5"))
      ).to.be.revertedWithCustomError(escrow, "OwnableUnauthorizedAccount");
    });

    it("Should revert with InvalidMaxAmount when setting to 0", async function () {
      await expect(
        escrow.connect(owner).setMaxEscrowAmount(0)
      ).to.be.revertedWithCustomError(escrow, "InvalidMaxAmount");
    });
  });

  // ═══════════════════════════════════════════════════════════════════════════
  // 3. createEscrow
  // ═══════════════════════════════════════════════════════════════════════════

  describe("createEscrow", function () {
    it("Should create an escrow with correct fields", async function () {
      const deadline = await futureDeadline();
      await escrow
        .connect(buyer)
        .createEscrow(provider.address, deadline, JOB_HASH, {
          value: ESCROW_AMOUNT,
        });

      const e = await escrow.getEscrow(0);
      expect(e.buyer).to.equal(buyer.address);
      expect(e.provider).to.equal(provider.address);
      expect(e.amount).to.equal(ESCROW_AMOUNT);
      expect(e.jobHash).to.equal(JOB_HASH);
      expect(e.state).to.equal(0); // EscrowState.Active
      expect(e.deadline).to.equal(deadline);
    });

    it("Should return escrowId 0 for the first escrow", async function () {
      const deadline = await futureDeadline();
      // Use staticCall to get the return value without sending a transaction
      const escrowId = await escrow
        .connect(buyer)
        .createEscrow.staticCall(provider.address, deadline, JOB_HASH, {
          value: ESCROW_AMOUNT,
        });
      expect(escrowId).to.equal(0);
    });

    it("Should increment escrowCount", async function () {
      expect(await escrow.escrowCount()).to.equal(0);

      const deadline = await futureDeadline();
      await escrow
        .connect(buyer)
        .createEscrow(provider.address, deadline, JOB_HASH, {
          value: ESCROW_AMOUNT,
        });
      expect(await escrow.escrowCount()).to.equal(1);

      await escrow
        .connect(buyer)
        .createEscrow(provider.address, deadline, JOB_HASH, {
          value: ESCROW_AMOUNT,
        });
      expect(await escrow.escrowCount()).to.equal(2);
    });

    it("Should emit EscrowCreated with correct args", async function () {
      const deadline = await futureDeadline();
      await expect(
        escrow
          .connect(buyer)
          .createEscrow(provider.address, deadline, JOB_HASH, {
            value: ESCROW_AMOUNT,
          })
      )
        .to.emit(escrow, "EscrowCreated")
        .withArgs(0, buyer.address, provider.address, ESCROW_AMOUNT, deadline, JOB_HASH);
    });

    it("Should set createdAt to current block timestamp", async function () {
      const deadline = await futureDeadline();
      await escrow
        .connect(buyer)
        .createEscrow(provider.address, deadline, JOB_HASH, {
          value: ESCROW_AMOUNT,
        });

      const e = await escrow.getEscrow(0);
      const latest = await time.latest();
      expect(e.createdAt).to.equal(latest);
    });

    it("Should revert with InvalidAddress when provider is address(0)", async function () {
      const deadline = await futureDeadline();
      await expect(
        escrow
          .connect(buyer)
          .createEscrow(ethers.ZeroAddress, deadline, JOB_HASH, {
            value: ESCROW_AMOUNT,
          })
      ).to.be.revertedWithCustomError(escrow, "InvalidAddress");
    });

    it("Should revert with InvalidAddress when provider is sender", async function () {
      const deadline = await futureDeadline();
      await expect(
        escrow
          .connect(buyer)
          .createEscrow(buyer.address, deadline, JOB_HASH, {
            value: ESCROW_AMOUNT,
          })
      ).to.be.revertedWithCustomError(escrow, "InvalidAddress");
    });

    it("Should revert with InvalidDeadline when deadline is in the past", async function () {
      const latest = await time.latest();
      const pastDeadline = latest - 100;
      await expect(
        escrow
          .connect(buyer)
          .createEscrow(provider.address, pastDeadline, JOB_HASH, {
            value: ESCROW_AMOUNT,
          })
      ).to.be.revertedWithCustomError(escrow, "InvalidDeadline");
    });

    it("Should revert with InvalidDeadline when deadline equals block.timestamp", async function () {
      // deadline <= block.timestamp reverts
      const latest = await time.latest();
      // The next block's timestamp will be latest+1, so set deadline = latest+1
      // to hit the exact boundary we need deadline == block.timestamp of the tx.
      // We increase time to make timestamp predictable:
      const nextTimestamp = latest + 1;
      await time.setNextBlockTimestamp(nextTimestamp);
      await expect(
        escrow
          .connect(buyer)
          .createEscrow(provider.address, nextTimestamp, JOB_HASH, {
            value: ESCROW_AMOUNT,
          })
      ).to.be.revertedWithCustomError(escrow, "InvalidDeadline");
    });

    it("Should revert with NoETHSent when msg.value is 0", async function () {
      const deadline = await futureDeadline();
      await expect(
        escrow
          .connect(buyer)
          .createEscrow(provider.address, deadline, JOB_HASH, { value: 0 })
      ).to.be.revertedWithCustomError(escrow, "NoETHSent");
    });

    it("Should revert with AmountTooLarge when value exceeds max", async function () {
      const deadline = await futureDeadline();
      const tooMuch = MAX_ESCROW + 1n;
      await expect(
        escrow
          .connect(buyer)
          .createEscrow(provider.address, deadline, JOB_HASH, {
            value: tooMuch,
          })
      ).to.be.revertedWithCustomError(escrow, "AmountTooLarge");
    });

    it("Should accept the exact max amount", async function () {
      const deadline = await futureDeadline();
      await expect(
        escrow
          .connect(buyer)
          .createEscrow(provider.address, deadline, JOB_HASH, {
            value: MAX_ESCROW,
          })
      ).to.not.be.reverted;
    });

    it("Should support multiple escrows with sequential IDs", async function () {
      const deadline = await futureDeadline();
      await escrow
        .connect(buyer)
        .createEscrow(provider.address, deadline, JOB_HASH, {
          value: ESCROW_AMOUNT,
        });
      await escrow
        .connect(buyer)
        .createEscrow(provider.address, deadline, JOB_HASH, {
          value: ESCROW_AMOUNT,
        });
      await escrow
        .connect(buyer)
        .createEscrow(provider.address, deadline, JOB_HASH, {
          value: ESCROW_AMOUNT,
        });

      expect(await escrow.escrowCount()).to.equal(3);

      const e0 = await escrow.getEscrow(0);
      const e1 = await escrow.getEscrow(1);
      const e2 = await escrow.getEscrow(2);
      expect(e0.buyer).to.equal(buyer.address);
      expect(e1.buyer).to.equal(buyer.address);
      expect(e2.buyer).to.equal(buyer.address);
    });

    it("Should lock ETH in the contract", async function () {
      const deadline = await futureDeadline();
      const contractAddr = await escrow.getAddress();

      const balanceBefore = await ethers.provider.getBalance(contractAddr);
      await escrow
        .connect(buyer)
        .createEscrow(provider.address, deadline, JOB_HASH, {
          value: ESCROW_AMOUNT,
        });
      const balanceAfter = await ethers.provider.getBalance(contractAddr);

      expect(balanceAfter - balanceBefore).to.equal(ESCROW_AMOUNT);
    });
  });

  // ═══════════════════════════════════════════════════════════════════════════
  // 4. releaseToProvider
  // ═══════════════════════════════════════════════════════════════════════════

  describe("releaseToProvider", function () {
    let escrowId: bigint;

    beforeEach(async function () {
      escrowId = await createDefaultEscrow();
    });

    it("Should transfer ETH to the provider", async function () {
      const providerBefore = await ethers.provider.getBalance(provider.address);

      await escrow.connect(buyer).releaseToProvider(escrowId);

      const providerAfter = await ethers.provider.getBalance(provider.address);
      expect(providerAfter - providerBefore).to.equal(ESCROW_AMOUNT);
    });

    it("Should set state to Released", async function () {
      await escrow.connect(buyer).releaseToProvider(escrowId);
      const e = await escrow.getEscrow(escrowId);
      expect(e.state).to.equal(1); // EscrowState.Released
    });

    it("Should emit EscrowReleased with correct args", async function () {
      await expect(escrow.connect(buyer).releaseToProvider(escrowId))
        .to.emit(escrow, "EscrowReleased")
        .withArgs(escrowId, provider.address, ESCROW_AMOUNT);
    });

    it("Should reduce contract ETH balance", async function () {
      const contractAddr = await escrow.getAddress();
      const balanceBefore = await ethers.provider.getBalance(contractAddr);

      await escrow.connect(buyer).releaseToProvider(escrowId);

      const balanceAfter = await ethers.provider.getBalance(contractAddr);
      expect(balanceBefore - balanceAfter).to.equal(ESCROW_AMOUNT);
    });

    it("Should revert with NotBuyer when called by non-buyer", async function () {
      await expect(
        escrow.connect(provider).releaseToProvider(escrowId)
      ).to.be.revertedWithCustomError(escrow, "NotBuyer");
    });

    it("Should revert with NotBuyer when called by stranger", async function () {
      await expect(
        escrow.connect(stranger).releaseToProvider(escrowId)
      ).to.be.revertedWithCustomError(escrow, "NotBuyer");
    });

    it("Should revert with EscrowNotActive when already released", async function () {
      await escrow.connect(buyer).releaseToProvider(escrowId);
      await expect(
        escrow.connect(buyer).releaseToProvider(escrowId)
      ).to.be.revertedWithCustomError(escrow, "EscrowNotActive");
    });

    it("Should revert with EscrowNotActive when already refunded", async function () {
      // Provider refunds
      await escrow.connect(provider).refundToBuyer(escrowId);
      await expect(
        escrow.connect(buyer).releaseToProvider(escrowId)
      ).to.be.revertedWithCustomError(escrow, "EscrowNotActive");
    });
  });

  // ═══════════════════════════════════════════════════════════════════════════
  // 5. refundToBuyer
  // ═══════════════════════════════════════════════════════════════════════════

  describe("refundToBuyer", function () {
    let escrowId: bigint;

    beforeEach(async function () {
      escrowId = await createDefaultEscrow();
    });

    describe("Provider refund (anytime)", function () {
      it("Should transfer ETH back to the buyer", async function () {
        const buyerBefore = await ethers.provider.getBalance(buyer.address);

        await escrow.connect(provider).refundToBuyer(escrowId);

        const buyerAfter = await ethers.provider.getBalance(buyer.address);
        expect(buyerAfter - buyerBefore).to.equal(ESCROW_AMOUNT);
      });

      it("Should set state to Refunded", async function () {
        await escrow.connect(provider).refundToBuyer(escrowId);
        const e = await escrow.getEscrow(escrowId);
        expect(e.state).to.equal(2); // EscrowState.Refunded
      });

      it("Should emit EscrowRefunded with correct args", async function () {
        await expect(escrow.connect(provider).refundToBuyer(escrowId))
          .to.emit(escrow, "EscrowRefunded")
          .withArgs(escrowId, buyer.address, ESCROW_AMOUNT);
      });

      it("Should work even before the deadline", async function () {
        // Provider can refund anytime -- no deadline check
        await expect(
          escrow.connect(provider).refundToBuyer(escrowId)
        ).to.not.be.reverted;
      });
    });

    describe("Buyer refund (after deadline)", function () {
      it("Should refund after deadline passes", async function () {
        // Advance time past the deadline
        const e = await escrow.getEscrow(escrowId);
        const deadlineVal = Number(e.deadline);
        await time.increaseTo(deadlineVal + 1);

        const buyerBefore = await ethers.provider.getBalance(buyer.address);

        const tx = await escrow.connect(buyer).refundToBuyer(escrowId);
        const receipt = await tx.wait();
        const gasCost = receipt!.gasUsed * receipt!.gasPrice;

        const buyerAfter = await ethers.provider.getBalance(buyer.address);
        // Account for gas cost
        expect(buyerAfter + gasCost - buyerBefore).to.equal(ESCROW_AMOUNT);
      });

      it("Should emit EscrowRefunded when buyer refunds", async function () {
        const e = await escrow.getEscrow(escrowId);
        await time.increaseTo(Number(e.deadline) + 1);

        await expect(escrow.connect(buyer).refundToBuyer(escrowId))
          .to.emit(escrow, "EscrowRefunded")
          .withArgs(escrowId, buyer.address, ESCROW_AMOUNT);
      });

      it("Should set state to Refunded when buyer refunds", async function () {
        const e = await escrow.getEscrow(escrowId);
        await time.increaseTo(Number(e.deadline) + 1);

        await escrow.connect(buyer).refundToBuyer(escrowId);

        const eAfter = await escrow.getEscrow(escrowId);
        expect(eAfter.state).to.equal(2); // EscrowState.Refunded
      });

      it("Should revert with DeadlineNotPassed when buyer refunds before deadline", async function () {
        // Deadline not yet passed
        await expect(
          escrow.connect(buyer).refundToBuyer(escrowId)
        ).to.be.revertedWithCustomError(escrow, "DeadlineNotPassed");
      });

      it("Should revert with DeadlineNotPassed when buyer refunds at exact deadline", async function () {
        const e = await escrow.getEscrow(escrowId);
        const deadlineVal = Number(e.deadline);
        // Use setNextBlockTimestamp so the tx executes at exactly the deadline.
        // Contract checks: block.timestamp <= deadline => revert DeadlineNotPassed
        await time.setNextBlockTimestamp(deadlineVal);

        await expect(
          escrow.connect(buyer).refundToBuyer(escrowId)
        ).to.be.revertedWithCustomError(escrow, "DeadlineNotPassed");
      });
    });

    describe("Stranger refund", function () {
      it("Should revert with NotBuyerOrProvider when called by stranger", async function () {
        await expect(
          escrow.connect(stranger).refundToBuyer(escrowId)
        ).to.be.revertedWithCustomError(escrow, "NotBuyerOrProvider");
      });
    });

    describe("Already-resolved escrow", function () {
      it("Should revert with EscrowNotActive when already released", async function () {
        await escrow.connect(buyer).releaseToProvider(escrowId);
        await expect(
          escrow.connect(provider).refundToBuyer(escrowId)
        ).to.be.revertedWithCustomError(escrow, "EscrowNotActive");
      });

      it("Should revert with EscrowNotActive when already refunded", async function () {
        await escrow.connect(provider).refundToBuyer(escrowId);
        await expect(
          escrow.connect(provider).refundToBuyer(escrowId)
        ).to.be.revertedWithCustomError(escrow, "EscrowNotActive");
      });
    });
  });

  // ═══════════════════════════════════════════════════════════════════════════
  // 6. getEscrow
  // ═══════════════════════════════════════════════════════════════════════════

  describe("getEscrow", function () {
    it("Should return correct data for an existing escrow", async function () {
      const deadline = await futureDeadline();
      await escrow
        .connect(buyer)
        .createEscrow(provider.address, deadline, JOB_HASH, {
          value: ESCROW_AMOUNT,
        });

      const e = await escrow.getEscrow(0);
      expect(e.buyer).to.equal(buyer.address);
      expect(e.provider).to.equal(provider.address);
      expect(e.amount).to.equal(ESCROW_AMOUNT);
      expect(e.jobHash).to.equal(JOB_HASH);
      expect(e.state).to.equal(0);
      expect(e.deadline).to.equal(deadline);
    });

    it("Should return default (zeroed) values for non-existent escrowId", async function () {
      const e = await escrow.getEscrow(999);
      expect(e.buyer).to.equal(ethers.ZeroAddress);
      expect(e.provider).to.equal(ethers.ZeroAddress);
      expect(e.amount).to.equal(0);
      expect(e.jobHash).to.equal(ethers.ZeroHash);
      expect(e.state).to.equal(0); // default enum value = Active
      expect(e.createdAt).to.equal(0);
      expect(e.deadline).to.equal(0);
    });
  });

  // ═══════════════════════════════════════════════════════════════════════════
  // 7. isActive
  // ═══════════════════════════════════════════════════════════════════════════

  describe("isActive", function () {
    it("Should return true for an Active escrow", async function () {
      await createDefaultEscrow();
      expect(await escrow.isActive(0)).to.be.true;
    });

    it("Should return false after release", async function () {
      const escrowId = await createDefaultEscrow();
      await escrow.connect(buyer).releaseToProvider(escrowId);
      expect(await escrow.isActive(escrowId)).to.be.false;
    });

    it("Should return false after refund", async function () {
      const escrowId = await createDefaultEscrow();
      await escrow.connect(provider).refundToBuyer(escrowId);
      expect(await escrow.isActive(escrowId)).to.be.false;
    });

    it("Should return true for non-existent escrowId (default state is Active=0)", async function () {
      // The default uint8 for EscrowState is 0 which maps to Active.
      // This is a known quirk -- the mapping returns a zeroed struct whose
      // state field defaults to the first enum member (Active).
      expect(await escrow.isActive(12345)).to.be.true;
    });
  });

  // ═══════════════════════════════════════════════════════════════════════════
  // 8. Edge cases & reentrancy
  // ═══════════════════════════════════════════════════════════════════════════

  describe("Edge cases", function () {
    it("Should accept exact max escrow amount", async function () {
      const deadline = await futureDeadline();
      await expect(
        escrow
          .connect(buyer)
          .createEscrow(provider.address, deadline, JOB_HASH, {
            value: MAX_ESCROW,
          })
      ).to.not.be.reverted;

      const e = await escrow.getEscrow(0);
      expect(e.amount).to.equal(MAX_ESCROW);
    });

    it("Should reject amount of max + 1 wei", async function () {
      const deadline = await futureDeadline();
      await expect(
        escrow
          .connect(buyer)
          .createEscrow(provider.address, deadline, JOB_HASH, {
            value: MAX_ESCROW + 1n,
          })
      ).to.be.revertedWithCustomError(escrow, "AmountTooLarge");
    });

    it("Should work correctly after maxEscrowAmount is increased", async function () {
      const newMax = ethers.parseEther("10");
      await escrow.connect(owner).setMaxEscrowAmount(newMax);

      const deadline = await futureDeadline();
      const bigAmount = ethers.parseEther("5");
      await expect(
        escrow
          .connect(buyer)
          .createEscrow(provider.address, deadline, JOB_HASH, {
            value: bigAmount,
          })
      ).to.not.be.reverted;
    });

    it("Should work correctly after maxEscrowAmount is decreased", async function () {
      const newMax = ethers.parseEther("0.1");
      await escrow.connect(owner).setMaxEscrowAmount(newMax);

      const deadline = await futureDeadline();
      await expect(
        escrow
          .connect(buyer)
          .createEscrow(provider.address, deadline, JOB_HASH, {
            value: ESCROW_AMOUNT, // 0.5 ETH > 0.1 ETH
          })
      ).to.be.revertedWithCustomError(escrow, "AmountTooLarge");
    });
  });

  describe("Reentrancy protection", function () {
    let attacker: ReentrancyAttacker;
    let attackerAddr: string;

    beforeEach(async function () {
      const AttackerFactory = await ethers.getContractFactory(
        "ReentrancyAttacker"
      );
      attacker = await AttackerFactory.deploy(await escrow.getAddress());
      attackerAddr = await attacker.getAddress();
    });

    it("Should prevent reentrancy on releaseToProvider", async function () {
      // Attacker contract is the provider so it receives ETH on release.
      // buyer creates escrow with attacker as provider.
      const deadline = await futureDeadline();
      await escrow
        .connect(buyer)
        .createEscrow(attackerAddr, deadline, JOB_HASH, {
          value: ESCROW_AMOUNT,
        });

      // Record attackCount before the release (may be non-zero from prior
      // ETH transfers that triggered receive()).
      const countBefore = await attacker.attackCount();

      // Buyer releases escrowId=0 -- ETH goes to attacker contract's receive()
      // which tries to re-enter releaseToProvider. The nonReentrant guard blocks it.
      await escrow.connect(buyer).releaseToProvider(0);

      // Verify: only one release happened; escrow 0 is Released.
      const e = await escrow.getEscrow(0);
      expect(e.state).to.equal(1); // Released

      // receive() was invoked exactly once for this release
      const countAfter = await attacker.attackCount();
      expect(countAfter - countBefore).to.equal(1n);
    });

    it("Should prevent reentrancy on refundToBuyer", async function () {
      // Attacker contract is the buyer. Provider is an EOA.
      // Fund attacker via its createEscrow function (payable) so we avoid
      // triggering receive() via a raw sendTransaction.
      const deadline = await futureDeadline();

      // Send ETH to attacker through the createEscrow call itself:
      // We need the attacker to hold ETH first. Use sendTransaction but
      // record the attackCount before the critical call.
      await owner.sendTransaction({
        to: attackerAddr,
        value: ESCROW_AMOUNT,
      });

      // Attacker creates escrow (attacker = buyer)
      await attacker.createEscrow(provider.address, deadline, JOB_HASH, {
        value: ESCROW_AMOUNT,
      });

      const escrowId = 0n;

      // Record attackCount before the refund
      const countBefore = await attacker.attackCount();

      // Provider refunds (ETH sent to attacker contract = buyer).
      // The attacker's receive() tries to re-enter refundToBuyer.
      // nonReentrant should block the re-entrance.
      await escrow.connect(provider).refundToBuyer(escrowId);

      // Verify the escrow was only refunded once
      const e = await escrow.getEscrow(escrowId);
      expect(e.state).to.equal(2); // Refunded

      // receive() was invoked exactly once for this refund
      const countAfter = await attacker.attackCount();
      expect(countAfter - countBefore).to.equal(1n);
    });

    it("Should not allow attacker to drain via re-entrant release", async function () {
      // Create two escrows where attacker is the provider.
      const deadline = await futureDeadline();

      await escrow
        .connect(buyer)
        .createEscrow(attackerAddr, deadline, JOB_HASH, {
          value: ESCROW_AMOUNT,
        });

      await escrow
        .connect(buyer)
        .createEscrow(attackerAddr, deadline, JOB_HASH, {
          value: ESCROW_AMOUNT,
        });

      const contractBalance = await ethers.provider.getBalance(
        await escrow.getAddress()
      );
      expect(contractBalance).to.equal(ESCROW_AMOUNT * 2n);

      // Buyer releases first escrow -- attacker receives ETH and tries re-entry
      await escrow.connect(buyer).releaseToProvider(0);

      // Second escrow should still be active (re-entry was blocked)
      const e1 = await escrow.getEscrow(1);
      expect(e1.state).to.equal(0); // Still Active

      // Contract still holds second escrow's funds
      const remainingBalance = await ethers.provider.getBalance(
        await escrow.getAddress()
      );
      expect(remainingBalance).to.equal(ESCROW_AMOUNT);
    });
  });

  // ═══════════════════════════════════════════════════════════════════════════
  // 9. TransferFailed coverage (ETH transfer rejection)
  // ═══════════════════════════════════════════════════════════════════════════

  describe("TransferFailed", function () {
    it("Should revert with TransferFailed when provider rejects ETH on release", async function () {
      // Deploy a contract with no receive/fallback as provider.
      // SimpleEscrow itself has no receive() function so it will reject ETH.
      const NoReceiveFactory = await ethers.getContractFactory("SimpleEscrow");
      const noReceiveContract = await NoReceiveFactory.deploy(MAX_ESCROW);
      const noReceiveAddr = await noReceiveContract.getAddress();

      const deadline = await futureDeadline();
      await escrow
        .connect(buyer)
        .createEscrow(noReceiveAddr, deadline, JOB_HASH, {
          value: ESCROW_AMOUNT,
        });

      // Attempting to release should fail because the provider contract
      // cannot accept ETH (no receive/fallback).
      await expect(
        escrow.connect(buyer).releaseToProvider(0)
      ).to.be.revertedWithCustomError(escrow, "TransferFailed");
    });

    it("Should revert with TransferFailed when buyer contract rejects ETH on refund", async function () {
      // Deploy ETHRejecter: can create escrows but has no receive/fallback.
      const RejecterFactory = await ethers.getContractFactory("ETHRejecter");
      const rejecter = await RejecterFactory.deploy(await escrow.getAddress());
      const rejecterAddr = await rejecter.getAddress();

      // Fund the rejecter so it can create an escrow
      // (ETHRejecter has no receive, but we can send ETH via createEscrow's
      //  msg.value -- the ETH goes directly to SimpleEscrow, not the rejecter.)
      const deadline = await futureDeadline();

      // Buyer sends value via the rejecter's createEscrow wrapper.
      // The rejecter becomes the buyer (msg.sender in SimpleEscrow).
      await rejecter.createEscrow(provider.address, deadline, JOB_HASH, {
        value: ESCROW_AMOUNT,
      });

      // Provider refunds: ETH goes to the rejecter (buyer), which has no
      // receive() -- transfer fails.
      await expect(
        escrow.connect(provider).refundToBuyer(0)
      ).to.be.revertedWithCustomError(escrow, "TransferFailed");
    });
  });

  // =========================================================================
  // 10. Pausable
  // =========================================================================

  describe("Pausable", function () {
    it("Should allow owner to pause", async function () {
      await escrow.pause();
      expect(await escrow.paused()).to.be.true;
    });

    it("Should allow owner to unpause", async function () {
      await escrow.pause();
      await escrow.unpause();
      expect(await escrow.paused()).to.be.false;
    });

    it("Should revert createEscrow when paused", async function () {
      await escrow.pause();
      const deadline = await futureDeadline();
      await expect(
        escrow.connect(buyer).createEscrow(provider.address, deadline, JOB_HASH, {
          value: ESCROW_AMOUNT,
        })
      ).to.be.revertedWithCustomError(escrow, "EnforcedPause");
    });

    it("Should allow releaseToProvider when paused (intentional)", async function () {
      // Create escrow before pausing
      await createDefaultEscrow();
      await escrow.pause();

      // Release should still work — existing escrows must be resolvable
      await expect(
        escrow.connect(buyer).releaseToProvider(0)
      ).to.not.be.reverted;
    });

    it("Should allow refundToBuyer when paused (intentional)", async function () {
      // Create escrow before pausing
      const deadline = await futureDeadline();
      await escrow.connect(buyer).createEscrow(provider.address, deadline, JOB_HASH, {
        value: ESCROW_AMOUNT,
      });
      await escrow.pause();

      // Provider can refund even when paused
      await expect(
        escrow.connect(provider).refundToBuyer(0)
      ).to.not.be.reverted;
    });

    it("Should revert pause when called by non-owner", async function () {
      await expect(
        escrow.connect(buyer).pause()
      ).to.be.revertedWithCustomError(escrow, "OwnableUnauthorizedAccount");
    });

    it("Should revert unpause when called by non-owner", async function () {
      await escrow.pause();
      await expect(
        escrow.connect(buyer).unpause()
      ).to.be.revertedWithCustomError(escrow, "OwnableUnauthorizedAccount");
    });

    it("Should resume normal operation after unpause", async function () {
      await escrow.pause();
      await escrow.unpause();

      const deadline = await futureDeadline();
      await expect(
        escrow.connect(buyer).createEscrow(provider.address, deadline, JOB_HASH, {
          value: ESCROW_AMOUNT,
        })
      ).to.not.be.reverted;
    });
  });
});
