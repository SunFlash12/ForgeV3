// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";

/**
 * @title CapsuleRegistry
 * @notice On-chain capsule hash anchoring for Forge knowledge capsules.
 *         Stores (capsuleId, contentHash, merkleRoot, capsuleType) per capsule
 *         and emits events for off-chain indexing and verification.
 * @dev Deployed to Base Sepolia for testnet lifecycle validation.
 */
contract CapsuleRegistry is Ownable {
    // ═══════════════════════════════════════════════════════════════════════
    // Types
    // ═══════════════════════════════════════════════════════════════════════

    struct CapsuleRecord {
        bytes32 contentHash;
        bytes32 merkleRoot;
        uint8 capsuleType;
        uint256 anchoredAt;
        address anchoredBy;
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
    ) external onlyOwner {
        if (contentHash == bytes32(0)) revert InvalidContentHash();
        if (capsules[capsuleId].anchoredAt != 0) {
            revert CapsuleAlreadyAnchored(capsuleId);
        }

        capsules[capsuleId] = CapsuleRecord({
            contentHash: contentHash,
            merkleRoot: merkleRoot,
            capsuleType: capsuleType,
            anchoredAt: block.timestamp,
            anchoredBy: msg.sender
        });

        capsuleCount++;

        emit CapsuleAnchored(
            capsuleId,
            contentHash,
            merkleRoot,
            capsuleType,
            msg.sender,
            block.timestamp
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
    ) external onlyOwner {
        uint256 len = capsuleIds.length;
        if (len == 0) revert EmptyBatch();
        if (
            contentHashes.length != len ||
            merkleRoots.length != len ||
            capsuleTypes.length != len
        ) {
            revert ArrayLengthMismatch();
        }

        for (uint256 i = 0; i < len; i++) {
            bytes32 cid = capsuleIds[i];
            if (contentHashes[i] == bytes32(0)) revert InvalidContentHash();
            if (capsules[cid].anchoredAt != 0) {
                revert CapsuleAlreadyAnchored(cid);
            }

            capsules[cid] = CapsuleRecord({
                contentHash: contentHashes[i],
                merkleRoot: merkleRoots[i],
                capsuleType: capsuleTypes[i],
                anchoredAt: block.timestamp,
                anchoredBy: msg.sender
            });

            capsuleCount++;

            emit CapsuleAnchored(
                cid,
                contentHashes[i],
                merkleRoots[i],
                capsuleTypes[i],
                msg.sender,
                block.timestamp
            );
        }

        emit BatchAnchored(len, msg.sender, block.timestamp);
    }

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
