// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/Pausable.sol";

/**
 * @title CapsuleRegistry
 * @notice On-chain capsule hash anchoring for Forge knowledge capsules.
 *         Stores (capsuleId, contentHash, merkleRoot, capsuleType) per capsule
 *         and emits events for off-chain indexing and verification.
 *
 * Gas optimizations:
 *   - Struct packed to 3 slots (down from 5): uint40 timestamp + uint8 type + address = 1 slot
 *   - unchecked arithmetic for counter increments (no overflow risk on uint256)
 *   - Batch anchor updates capsuleCount once instead of per-iteration
 *   - calldata arrays avoid memory copies
 */
contract CapsuleRegistry is Ownable, Pausable {
    // ═══════════════════════════════════════════════════════════════════════
    // Types
    // ═══════════════════════════════════════════════════════════════════════

    struct CapsuleRecord {
        bytes32 contentHash;   // slot 0: 32 bytes
        bytes32 merkleRoot;    // slot 1: 32 bytes
        uint40 anchoredAt;     // slot 2: 5 bytes  (unix ts — good until year 36812)
        uint8 capsuleType;     // slot 2: 1 byte   (packed)
        address anchoredBy;    // slot 2: 20 bytes  (packed) — total 26/32 bytes
    }

    // ═══════════════════════════════════════════════════════════════════════
    // State
    // ═══════════════════════════════════════════════════════════════════════

    /// @notice capsuleId => CapsuleRecord
    mapping(bytes32 => CapsuleRecord) public capsules;

    /// @notice Total number of anchored capsules
    uint256 public capsuleCount;

    // ═══════════════════════════════════════════════════════════════════════
    // Events
    // ═══════════════════════════════════════════════════════════════════════

    event CapsuleAnchored(
        bytes32 indexed capsuleId,
        bytes32 contentHash,
        bytes32 merkleRoot,
        uint8 capsuleType,
        address indexed anchoredBy,
        uint256 timestamp
    );

    event BatchAnchored(
        uint256 count,
        address indexed anchoredBy,
        uint256 timestamp
    );

    // ═══════════════════════════════════════════════════════════════════════
    // Errors
    // ═══════════════════════════════════════════════════════════════════════

    error CapsuleAlreadyAnchored(bytes32 capsuleId);
    error CapsuleNotFound(bytes32 capsuleId);
    error EmptyBatch();
    error ArrayLengthMismatch();
    error InvalidContentHash();

    // ═══════════════════════════════════════════════════════════════════════
    // Constructor
    // ═══════════════════════════════════════════════════════════════════════

    constructor() Ownable(msg.sender) {}

    // ═══════════════════════════════════════════════════════════════════════
    // External Functions
    // ═══════════════════════════════════════════════════════════════════════

    /**
     * @notice Anchor a single capsule's content hash on-chain.
     * @param capsuleId   Unique identifier for the capsule (SHA-256 of capsule name)
     * @param contentHash SHA-256 hash of the capsule's full content
     * @param merkleRoot  Merkle root of the capsule's lineage chain
     * @param capsuleType Numeric type (0=KNOWLEDGE, 1=INSIGHT, ..., 10=DOCUMENT)
     */
    function anchorCapsule(
        bytes32 capsuleId,
        bytes32 contentHash,
        bytes32 merkleRoot,
        uint8 capsuleType
    ) external onlyOwner whenNotPaused {
        if (contentHash == bytes32(0)) revert InvalidContentHash();
        if (capsules[capsuleId].anchoredAt != 0) {
            revert CapsuleAlreadyAnchored(capsuleId);
        }

        uint40 ts = uint40(block.timestamp);

        capsules[capsuleId] = CapsuleRecord({
            contentHash: contentHash,
            merkleRoot: merkleRoot,
            anchoredAt: ts,
            capsuleType: capsuleType,
            anchoredBy: msg.sender
        });

        unchecked { capsuleCount++; }

        emit CapsuleAnchored(
            capsuleId,
            contentHash,
            merkleRoot,
            capsuleType,
            msg.sender,
            ts
        );
    }

    /**
     * @notice Anchor multiple capsules in a single transaction.
     * @param capsuleIds    Array of capsule identifiers
     * @param contentHashes Array of content hashes
     * @param merkleRoots   Array of merkle roots
     * @param capsuleTypes  Array of capsule types
     */
    function batchAnchor(
        bytes32[] calldata capsuleIds,
        bytes32[] calldata contentHashes,
        bytes32[] calldata merkleRoots,
        uint8[] calldata capsuleTypes
    ) external onlyOwner whenNotPaused {
        uint256 len = capsuleIds.length;
        if (len == 0) revert EmptyBatch();
        if (
            contentHashes.length != len ||
            merkleRoots.length != len ||
            capsuleTypes.length != len
        ) {
            revert ArrayLengthMismatch();
        }

        uint40 ts = uint40(block.timestamp);

        for (uint256 i; i < len; ) {
            bytes32 cid = capsuleIds[i];
            bytes32 ch = contentHashes[i];
            if (ch == bytes32(0)) revert InvalidContentHash();
            if (capsules[cid].anchoredAt != 0) {
                revert CapsuleAlreadyAnchored(cid);
            }

            capsules[cid] = CapsuleRecord({
                contentHash: ch,
                merkleRoot: merkleRoots[i],
                anchoredAt: ts,
                capsuleType: capsuleTypes[i],
                anchoredBy: msg.sender
            });

            emit CapsuleAnchored(
                cid,
                ch,
                merkleRoots[i],
                capsuleTypes[i],
                msg.sender,
                ts
            );

            unchecked { ++i; }
        }

        unchecked { capsuleCount += len; }

        emit BatchAnchored(len, msg.sender, ts);
    }

    // ═══════════════════════════════════════════════════════════════════════
    // Pause Functions
    // ═══════════════════════════════════════════════════════════════════════

    function pause() external onlyOwner { _pause(); }
    function unpause() external onlyOwner { _unpause(); }

    // ═══════════════════════════════════════════════════════════════════════
    // View Functions
    // ═══════════════════════════════════════════════════════════════════════

    /**
     * @notice Verify that a capsule's content hash matches the anchored record.
     * @param capsuleId   The capsule to verify
     * @param contentHash The content hash to check against
     * @return True if the content hash matches the anchored record
     */
    function verifyCapsule(
        bytes32 capsuleId,
        bytes32 contentHash
    ) external view returns (bool) {
        CapsuleRecord storage record = capsules[capsuleId];
        if (record.anchoredAt == 0) revert CapsuleNotFound(capsuleId);
        return record.contentHash == contentHash;
    }

    /**
     * @notice Get the full record for an anchored capsule.
     * @param capsuleId The capsule to look up
     * @return The CapsuleRecord struct
     */
    function getCapsule(
        bytes32 capsuleId
    ) external view returns (CapsuleRecord memory) {
        CapsuleRecord storage record = capsules[capsuleId];
        if (record.anchoredAt == 0) revert CapsuleNotFound(capsuleId);
        return record;
    }

    /**
     * @notice Check whether a capsule has been anchored.
     * @param capsuleId The capsule to check
     * @return True if the capsule exists in the registry
     */
    function isAnchored(bytes32 capsuleId) external view returns (bool) {
        return capsules[capsuleId].anchoredAt != 0;
    }
}
