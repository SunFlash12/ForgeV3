import { expect } from "chai";
import { ethers } from "hardhat";
import { CapsuleRegistry } from "../typechain-types";
import { SignerWithAddress } from "@nomicfoundation/hardhat-ethers/signers";

describe("CapsuleRegistry", function () {
  let registry: CapsuleRegistry;
  let owner: SignerWithAddress;
  let nonOwner: SignerWithAddress;

  // Deterministic test fixtures
  const CAPSULE_ID = ethers.id("capsule-001");
  const CONTENT_HASH = ethers.id("content-of-capsule-001");
  const MERKLE_ROOT = ethers.id("merkle-root-001");
  const CAPSULE_TYPE = 1; // INSIGHT

  const ZERO_BYTES32 = ethers.ZeroHash;

  beforeEach(async function () {
    [owner, nonOwner] = await ethers.getSigners();

    const Factory = await ethers.getContractFactory("CapsuleRegistry");
    registry = await Factory.deploy();
  });

  // =========================================================================
  // 1. Deployment
  // =========================================================================

  describe("Deployment", function () {
    it("Should set deployer as owner", async function () {
      expect(await registry.owner()).to.equal(owner.address);
    });

    it("Should initialize capsuleCount to 0", async function () {
      expect(await registry.capsuleCount()).to.equal(0);
    });
  });

  // =========================================================================
  // 2. anchorCapsule
  // =========================================================================

  describe("anchorCapsule", function () {
    it("Should anchor a capsule and store the correct record", async function () {
      await registry.anchorCapsule(CAPSULE_ID, CONTENT_HASH, MERKLE_ROOT, CAPSULE_TYPE);

      const record = await registry.getCapsule(CAPSULE_ID);
      expect(record.contentHash).to.equal(CONTENT_HASH);
      expect(record.merkleRoot).to.equal(MERKLE_ROOT);
      expect(record.capsuleType).to.equal(CAPSULE_TYPE);
      expect(record.anchoredBy).to.equal(owner.address);
      expect(record.anchoredAt).to.be.gt(0);
    });

    it("Should emit CapsuleAnchored event with correct args", async function () {
      const tx = registry.anchorCapsule(CAPSULE_ID, CONTENT_HASH, MERKLE_ROOT, CAPSULE_TYPE);

      await expect(tx)
        .to.emit(registry, "CapsuleAnchored")
        .withArgs(
          CAPSULE_ID,
          CONTENT_HASH,
          MERKLE_ROOT,
          CAPSULE_TYPE,
          owner.address,
          // timestamp is block.timestamp cast to uint40; we accept any non-zero value
          (val: bigint) => val > 0n
        );
    });

    it("Should increment capsuleCount by 1", async function () {
      expect(await registry.capsuleCount()).to.equal(0);
      await registry.anchorCapsule(CAPSULE_ID, CONTENT_HASH, MERKLE_ROOT, CAPSULE_TYPE);
      expect(await registry.capsuleCount()).to.equal(1);
    });

    it("Should revert with CapsuleAlreadyAnchored on duplicate", async function () {
      await registry.anchorCapsule(CAPSULE_ID, CONTENT_HASH, MERKLE_ROOT, CAPSULE_TYPE);

      await expect(
        registry.anchorCapsule(CAPSULE_ID, CONTENT_HASH, MERKLE_ROOT, CAPSULE_TYPE)
      ).to.be.revertedWithCustomError(registry, "CapsuleAlreadyAnchored")
        .withArgs(CAPSULE_ID);
    });

    it("Should revert with InvalidContentHash when contentHash is zero", async function () {
      await expect(
        registry.anchorCapsule(CAPSULE_ID, ZERO_BYTES32, MERKLE_ROOT, CAPSULE_TYPE)
      ).to.be.revertedWithCustomError(registry, "InvalidContentHash");
    });

    it("Should revert with OwnableUnauthorizedAccount for non-owner", async function () {
      await expect(
        registry.connect(nonOwner).anchorCapsule(CAPSULE_ID, CONTENT_HASH, MERKLE_ROOT, CAPSULE_TYPE)
      ).to.be.revertedWithCustomError(registry, "OwnableUnauthorizedAccount");
    });
  });

  // =========================================================================
  // 3. batchAnchor
  // =========================================================================

  describe("batchAnchor", function () {
    // Helper to create N unique capsule parameters
    function makeBatch(n: number) {
      const ids: string[] = [];
      const hashes: string[] = [];
      const roots: string[] = [];
      const types: number[] = [];
      for (let i = 0; i < n; i++) {
        ids.push(ethers.id(`batch-capsule-${i}`));
        hashes.push(ethers.id(`batch-content-${i}`));
        roots.push(ethers.id(`batch-merkle-${i}`));
        types.push(i % 11); // cycle through types 0-10
      }
      return { ids, hashes, roots, types };
    }

    it("Should anchor a batch of 3 capsules", async function () {
      const { ids, hashes, roots, types } = makeBatch(3);
      await registry.batchAnchor(ids, hashes, roots, types);

      // Verify each capsule was stored
      for (let i = 0; i < 3; i++) {
        const record = await registry.getCapsule(ids[i]);
        expect(record.contentHash).to.equal(hashes[i]);
        expect(record.merkleRoot).to.equal(roots[i]);
        expect(record.capsuleType).to.equal(types[i]);
        expect(record.anchoredBy).to.equal(owner.address);
        expect(record.anchoredAt).to.be.gt(0);
      }
    });

    it("Should increment capsuleCount by the batch size", async function () {
      const { ids, hashes, roots, types } = makeBatch(3);
      expect(await registry.capsuleCount()).to.equal(0);

      await registry.batchAnchor(ids, hashes, roots, types);

      expect(await registry.capsuleCount()).to.equal(3);
    });

    it("Should emit CapsuleAnchored for each item in the batch", async function () {
      const { ids, hashes, roots, types } = makeBatch(3);
      const tx = registry.batchAnchor(ids, hashes, roots, types);

      for (let i = 0; i < 3; i++) {
        await expect(tx)
          .to.emit(registry, "CapsuleAnchored")
          .withArgs(
            ids[i],
            hashes[i],
            roots[i],
            types[i],
            owner.address,
            (val: bigint) => val > 0n
          );
      }
    });

    it("Should emit BatchAnchored event with correct count", async function () {
      const { ids, hashes, roots, types } = makeBatch(3);
      const tx = registry.batchAnchor(ids, hashes, roots, types);

      await expect(tx)
        .to.emit(registry, "BatchAnchored")
        .withArgs(
          3,
          owner.address,
          (val: bigint) => val > 0n
        );
    });

    it("Should revert with EmptyBatch when arrays are empty", async function () {
      await expect(
        registry.batchAnchor([], [], [], [])
      ).to.be.revertedWithCustomError(registry, "EmptyBatch");
    });

    it("Should revert with ArrayLengthMismatch when contentHashes length differs", async function () {
      const id = [ethers.id("a")];
      await expect(
        registry.batchAnchor(id, [], [ethers.id("r")], [0])
      ).to.be.revertedWithCustomError(registry, "ArrayLengthMismatch");
    });

    it("Should revert with ArrayLengthMismatch when merkleRoots length differs", async function () {
      const id = [ethers.id("a")];
      const hash = [ethers.id("h")];
      await expect(
        registry.batchAnchor(id, hash, [], [0])
      ).to.be.revertedWithCustomError(registry, "ArrayLengthMismatch");
    });

    it("Should revert with ArrayLengthMismatch when capsuleTypes length differs", async function () {
      const id = [ethers.id("a")];
      const hash = [ethers.id("h")];
      const root = [ethers.id("r")];
      await expect(
        registry.batchAnchor(id, hash, root, [])
      ).to.be.revertedWithCustomError(registry, "ArrayLengthMismatch");
    });

    it("Should revert with InvalidContentHash if any element has zero contentHash", async function () {
      const ids = [ethers.id("a"), ethers.id("b")];
      const hashes = [ethers.id("h1"), ZERO_BYTES32]; // second is zero
      const roots = [ethers.id("r1"), ethers.id("r2")];
      const types = [0, 1];

      await expect(
        registry.batchAnchor(ids, hashes, roots, types)
      ).to.be.revertedWithCustomError(registry, "InvalidContentHash");
    });

    it("Should revert with CapsuleAlreadyAnchored if a capsule in the batch was already anchored", async function () {
      // Anchor one capsule first
      const existingId = ethers.id("existing");
      const existingHash = ethers.id("existing-content");
      await registry.anchorCapsule(existingId, existingHash, ethers.id("mr"), 0);

      // Attempt batch that includes the already-anchored capsule
      const ids = [ethers.id("new-one"), existingId];
      const hashes = [ethers.id("h-new"), ethers.id("h-existing")];
      const roots = [ethers.id("r-new"), ethers.id("r-existing")];
      const types = [1, 2];

      await expect(
        registry.batchAnchor(ids, hashes, roots, types)
      ).to.be.revertedWithCustomError(registry, "CapsuleAlreadyAnchored")
        .withArgs(existingId);
    });

    it("Should revert with OwnableUnauthorizedAccount for non-owner", async function () {
      const { ids, hashes, roots, types } = makeBatch(1);

      await expect(
        registry.connect(nonOwner).batchAnchor(ids, hashes, roots, types)
      ).to.be.revertedWithCustomError(registry, "OwnableUnauthorizedAccount");
    });
  });

  // =========================================================================
  // 4. verifyCapsule
  // =========================================================================

  describe("verifyCapsule", function () {
    beforeEach(async function () {
      await registry.anchorCapsule(CAPSULE_ID, CONTENT_HASH, MERKLE_ROOT, CAPSULE_TYPE);
    });

    it("Should return true when contentHash matches", async function () {
      expect(await registry.verifyCapsule(CAPSULE_ID, CONTENT_HASH)).to.be.true;
    });

    it("Should return false when contentHash does not match", async function () {
      const wrongHash = ethers.id("wrong-content");
      expect(await registry.verifyCapsule(CAPSULE_ID, wrongHash)).to.be.false;
    });

    it("Should revert with CapsuleNotFound for non-existent capsule", async function () {
      const unknownId = ethers.id("unknown-capsule");
      await expect(
        registry.verifyCapsule(unknownId, CONTENT_HASH)
      ).to.be.revertedWithCustomError(registry, "CapsuleNotFound")
        .withArgs(unknownId);
    });
  });

  // =========================================================================
  // 5. getCapsule
  // =========================================================================

  describe("getCapsule", function () {
    it("Should return correct record fields", async function () {
      const tx = await registry.anchorCapsule(CAPSULE_ID, CONTENT_HASH, MERKLE_ROOT, CAPSULE_TYPE);
      const receipt = await tx.wait();
      const block = await ethers.provider.getBlock(receipt!.blockNumber);
      const expectedTimestamp = block!.timestamp;

      const record = await registry.getCapsule(CAPSULE_ID);
      expect(record.contentHash).to.equal(CONTENT_HASH);
      expect(record.merkleRoot).to.equal(MERKLE_ROOT);
      // anchoredAt is uint40(block.timestamp)
      expect(record.anchoredAt).to.equal(expectedTimestamp);
      expect(record.capsuleType).to.equal(CAPSULE_TYPE);
      expect(record.anchoredBy).to.equal(owner.address);
    });

    it("Should revert with CapsuleNotFound for non-existent capsule", async function () {
      const unknownId = ethers.id("does-not-exist");
      await expect(
        registry.getCapsule(unknownId)
      ).to.be.revertedWithCustomError(registry, "CapsuleNotFound")
        .withArgs(unknownId);
    });
  });

  // =========================================================================
  // 6. isAnchored
  // =========================================================================

  describe("isAnchored", function () {
    it("Should return true for an anchored capsule", async function () {
      await registry.anchorCapsule(CAPSULE_ID, CONTENT_HASH, MERKLE_ROOT, CAPSULE_TYPE);
      expect(await registry.isAnchored(CAPSULE_ID)).to.be.true;
    });

    it("Should return false for a non-existent capsule", async function () {
      const unknownId = ethers.id("never-anchored");
      expect(await registry.isAnchored(unknownId)).to.be.false;
    });
  });

  // =========================================================================
  // 7. Edge cases
  // =========================================================================

  describe("Edge cases", function () {
    it("Should allow anchoring with merkleRoot = bytes32(0)", async function () {
      // merkleRoot of zero is valid (no lineage tree yet)
      await expect(
        registry.anchorCapsule(CAPSULE_ID, CONTENT_HASH, ZERO_BYTES32, CAPSULE_TYPE)
      ).to.not.be.reverted;

      const record = await registry.getCapsule(CAPSULE_ID);
      expect(record.merkleRoot).to.equal(ZERO_BYTES32);
    });

    it("Should handle max uint8 capsuleType (255)", async function () {
      const maxType = 255;
      await registry.anchorCapsule(CAPSULE_ID, CONTENT_HASH, MERKLE_ROOT, maxType);

      const record = await registry.getCapsule(CAPSULE_ID);
      expect(record.capsuleType).to.equal(maxType);
    });

    it("Should handle a large batch of 20 items", async function () {
      const ids: string[] = [];
      const hashes: string[] = [];
      const roots: string[] = [];
      const types: number[] = [];

      for (let i = 0; i < 20; i++) {
        ids.push(ethers.id(`large-batch-${i}`));
        hashes.push(ethers.id(`large-content-${i}`));
        roots.push(ethers.id(`large-root-${i}`));
        types.push(i % 256);
      }

      await registry.batchAnchor(ids, hashes, roots, types);

      expect(await registry.capsuleCount()).to.equal(20);

      // Spot-check first and last
      const first = await registry.getCapsule(ids[0]);
      expect(first.contentHash).to.equal(hashes[0]);
      expect(first.capsuleType).to.equal(types[0]);

      const last = await registry.getCapsule(ids[19]);
      expect(last.contentHash).to.equal(hashes[19]);
      expect(last.capsuleType).to.equal(types[19]);
    });

    it("Should correctly accumulate capsuleCount across mixed single and batch anchors", async function () {
      // Anchor 1 single
      await registry.anchorCapsule(
        ethers.id("solo-1"),
        ethers.id("solo-content-1"),
        ethers.id("solo-root-1"),
        0
      );
      expect(await registry.capsuleCount()).to.equal(1);

      // Batch anchor 2
      await registry.batchAnchor(
        [ethers.id("batch-a"), ethers.id("batch-b")],
        [ethers.id("content-a"), ethers.id("content-b")],
        [ethers.id("root-a"), ethers.id("root-b")],
        [1, 2]
      );
      expect(await registry.capsuleCount()).to.equal(3);

      // Anchor 1 more single
      await registry.anchorCapsule(
        ethers.id("solo-2"),
        ethers.id("solo-content-2"),
        ethers.id("solo-root-2"),
        3
      );
      expect(await registry.capsuleCount()).to.equal(4);
    });

    it("Should store distinct records for different capsuleIds", async function () {
      const id1 = ethers.id("capsule-alpha");
      const id2 = ethers.id("capsule-beta");
      const hash1 = ethers.id("content-alpha");
      const hash2 = ethers.id("content-beta");

      await registry.anchorCapsule(id1, hash1, MERKLE_ROOT, 0);
      await registry.anchorCapsule(id2, hash2, MERKLE_ROOT, 5);

      const r1 = await registry.getCapsule(id1);
      const r2 = await registry.getCapsule(id2);

      expect(r1.contentHash).to.equal(hash1);
      expect(r1.capsuleType).to.equal(0);

      expect(r2.contentHash).to.equal(hash2);
      expect(r2.capsuleType).to.equal(5);
    });

    it("Should revert batch with duplicate capsuleIds within the same batch", async function () {
      const duplicateId = ethers.id("dup");
      const ids = [duplicateId, duplicateId];
      const hashes = [ethers.id("h1"), ethers.id("h2")];
      const roots = [ethers.id("r1"), ethers.id("r2")];
      const types = [0, 1];

      // The second element will revert because the first was anchored in the same tx
      await expect(
        registry.batchAnchor(ids, hashes, roots, types)
      ).to.be.revertedWithCustomError(registry, "CapsuleAlreadyAnchored")
        .withArgs(duplicateId);
    });
  });

  // =========================================================================
  // 7. Pausable
  // =========================================================================

  describe("Pausable", function () {
    it("Should allow owner to pause", async function () {
      await registry.pause();
      expect(await registry.paused()).to.be.true;
    });

    it("Should allow owner to unpause", async function () {
      await registry.pause();
      await registry.unpause();
      expect(await registry.paused()).to.be.false;
    });

    it("Should revert anchorCapsule when paused", async function () {
      await registry.pause();
      await expect(
        registry.anchorCapsule(CAPSULE_ID, CONTENT_HASH, MERKLE_ROOT, CAPSULE_TYPE)
      ).to.be.revertedWithCustomError(registry, "EnforcedPause");
    });

    it("Should revert batchAnchor when paused", async function () {
      await registry.pause();
      await expect(
        registry.batchAnchor([CAPSULE_ID], [CONTENT_HASH], [MERKLE_ROOT], [CAPSULE_TYPE])
      ).to.be.revertedWithCustomError(registry, "EnforcedPause");
    });

    it("Should allow reads when paused", async function () {
      // Anchor first, then pause
      await registry.anchorCapsule(CAPSULE_ID, CONTENT_HASH, MERKLE_ROOT, CAPSULE_TYPE);
      await registry.pause();

      // Read operations should still work
      expect(await registry.isAnchored(CAPSULE_ID)).to.be.true;
      expect(await registry.verifyCapsule(CAPSULE_ID, CONTENT_HASH)).to.be.true;
      const record = await registry.getCapsule(CAPSULE_ID);
      expect(record.contentHash).to.equal(CONTENT_HASH);
    });

    it("Should revert pause when called by non-owner", async function () {
      await expect(
        registry.connect(nonOwner).pause()
      ).to.be.revertedWithCustomError(registry, "OwnableUnauthorizedAccount");
    });

    it("Should revert unpause when called by non-owner", async function () {
      await registry.pause();
      await expect(
        registry.connect(nonOwner).unpause()
      ).to.be.revertedWithCustomError(registry, "OwnableUnauthorizedAccount");
    });

    it("Should resume normal operation after unpause", async function () {
      await registry.pause();
      await registry.unpause();

      // Should work again
      await expect(
        registry.anchorCapsule(CAPSULE_ID, CONTENT_HASH, MERKLE_ROOT, CAPSULE_TYPE)
      ).to.not.be.reverted;
    });
  });
});
