// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/Pausable.sol";

/**
 * @title SimpleEscrow
 * @notice ETH-based escrow for ACP (Agent Communication Protocol) job lifecycle.
 *         Buyer locks ETH when creating an escrow. The buyer can release funds
 *         to the provider upon job completion, or the provider/buyer can trigger
 *         a refund if the job is rejected or the deadline passes.
 *
 * Gas optimizations:
 *   - Struct packed to 4 slots (down from 7):
 *       slot 0: buyer(20) + state(1) + createdAt(5) = 26 bytes
 *       slot 1: provider(20) + deadline(5) = 25 bytes
 *       slot 2: amount(32)
 *       slot 3: jobHash(32)
 *   - unchecked arithmetic for counter (no overflow on uint256)
 *   - Local variable caching for storage reads
 *   - maxEscrowAmount configurable by owner (not hardcoded constant)
 */
contract SimpleEscrow is ReentrancyGuard, Ownable, Pausable {
    // ═══════════════════════════════════════════════════════════════════════
    // Types
    // ═══════════════════════════════════════════════════════════════════════

    enum EscrowState {
        Active,     // ETH locked, job in progress
        Released,   // Buyer approved, ETH sent to provider
        Refunded    // Job rejected or deadline passed, ETH returned to buyer
    }

    struct Escrow {
        address buyer;         // slot 0: 20 bytes
        EscrowState state;     // slot 0: 1 byte   (packed)
        uint40 createdAt;      // slot 0: 5 bytes   (packed) — good until year 36812
        address provider;      // slot 1: 20 bytes
        uint40 deadline;       // slot 1: 5 bytes   (packed)
        uint256 amount;        // slot 2: 32 bytes
        bytes32 jobHash;       // slot 3: 32 bytes
    }

    // ═══════════════════════════════════════════════════════════════════════
    // State
    // ═══════════════════════════════════════════════════════════════════════

    /// @notice escrowId => Escrow
    mapping(uint256 => Escrow) public escrows;

    /// @notice Auto-incrementing escrow counter
    uint256 public escrowCount;

    /// @notice Maximum ETH per escrow (configurable by owner)
    uint256 public maxEscrowAmount;

    // ═══════════════════════════════════════════════════════════════════════
    // Events
    // ═══════════════════════════════════════════════════════════════════════

    event EscrowCreated(
        uint256 indexed escrowId,
        address indexed buyer,
        address indexed provider,
        uint256 amount,
        uint256 deadline,
        bytes32 jobHash
    );

    event EscrowReleased(
        uint256 indexed escrowId,
        address indexed provider,
        uint256 amount
    );

    event EscrowRefunded(
        uint256 indexed escrowId,
        address indexed buyer,
        uint256 amount
    );

    event MaxEscrowAmountUpdated(
        uint256 oldAmount,
        uint256 newAmount
    );

    // ═══════════════════════════════════════════════════════════════════════
    // Errors
    // ═══════════════════════════════════════════════════════════════════════

    error InvalidAddress();
    error InvalidDeadline();
    error AmountTooLarge();
    error NoETHSent();
    error EscrowNotActive();
    error NotBuyer();
    error NotBuyerOrProvider();
    error DeadlineNotPassed();
    error TransferFailed();
    error InvalidMaxAmount();

    // ═══════════════════════════════════════════════════════════════════════
    // Constructor
    // ═══════════════════════════════════════════════════════════════════════

    /**
     * @param _maxEscrowAmount Initial maximum ETH per escrow (e.g. 0.01 ether for testnet)
     */
    constructor(uint256 _maxEscrowAmount) Ownable(msg.sender) {
        if (_maxEscrowAmount == 0) revert InvalidMaxAmount();
        maxEscrowAmount = _maxEscrowAmount;
    }

    // ═══════════════════════════════════════════════════════════════════════
    // Owner Functions
    // ═══════════════════════════════════════════════════════════════════════

    /**
     * @notice Update the maximum ETH allowed per escrow.
     * @param _newMax New maximum amount in wei
     */
    function setMaxEscrowAmount(uint256 _newMax) external onlyOwner {
        if (_newMax == 0) revert InvalidMaxAmount();
        uint256 oldMax = maxEscrowAmount;
        maxEscrowAmount = _newMax;
        emit MaxEscrowAmountUpdated(oldMax, _newMax);
    }

    function pause() external onlyOwner { _pause(); }
    function unpause() external onlyOwner { _unpause(); }

    // ═══════════════════════════════════════════════════════════════════════
    // External Functions
    // ═══════════════════════════════════════════════════════════════════════

    /**
     * @notice Create a new escrow by locking ETH.
     * @param provider The address that will receive payment on completion
     * @param deadline Unix timestamp after which a refund becomes available
     * @param jobHash  Hash of the ACP job description for on-chain reference
     * @return escrowId The ID of the newly created escrow
     */
    function createEscrow(
        address provider,
        uint256 deadline,
        bytes32 jobHash
    ) external payable nonReentrant whenNotPaused returns (uint256 escrowId) {
        if (provider == address(0)) revert InvalidAddress();
        if (provider == msg.sender) revert InvalidAddress();
        if (deadline <= block.timestamp) revert InvalidDeadline();
        if (msg.value == 0) revert NoETHSent();
        if (msg.value > maxEscrowAmount) revert AmountTooLarge();

        uint256 count;
        unchecked { count = escrowCount++; }
        escrowId = count;

        escrows[escrowId] = Escrow({
            buyer: msg.sender,
            state: EscrowState.Active,
            createdAt: uint40(block.timestamp),
            provider: provider,
            deadline: uint40(deadline),
            amount: msg.value,
            jobHash: jobHash
        });

        emit EscrowCreated(
            escrowId,
            msg.sender,
            provider,
            msg.value,
            deadline,
            jobHash
        );
    }

    /**
     * @notice Release escrowed ETH to the provider (buyer approves job completion).
     * @param escrowId The escrow to release
     */
    function releaseToProvider(uint256 escrowId) external nonReentrant {
        Escrow storage e = escrows[escrowId];
        if (e.state != EscrowState.Active) revert EscrowNotActive();
        if (msg.sender != e.buyer) revert NotBuyer();

        e.state = EscrowState.Released;

        uint256 amt = e.amount;
        address provider = e.provider;

        (bool success, ) = payable(provider).call{value: amt}("");
        if (!success) revert TransferFailed();

        emit EscrowReleased(escrowId, provider, amt);
    }

    /**
     * @notice Refund escrowed ETH to the buyer.
     *         - The provider can refund at any time (job rejection).
     *         - The buyer can refund only after the deadline has passed.
     * @param escrowId The escrow to refund
     */
    function refundToBuyer(uint256 escrowId) external nonReentrant {
        Escrow storage e = escrows[escrowId];
        if (e.state != EscrowState.Active) revert EscrowNotActive();

        address buyer = e.buyer;
        if (msg.sender == e.provider) {
            // Provider can refund anytime (job rejection)
        } else if (msg.sender == buyer) {
            // Buyer can only refund after deadline
            if (block.timestamp <= uint256(e.deadline)) revert DeadlineNotPassed();
        } else {
            revert NotBuyerOrProvider();
        }

        e.state = EscrowState.Refunded;

        uint256 amt = e.amount;

        (bool success, ) = payable(buyer).call{value: amt}("");
        if (!success) revert TransferFailed();

        emit EscrowRefunded(escrowId, buyer, amt);
    }

    // ═══════════════════════════════════════════════════════════════════════
    // View Functions
    // ═══════════════════════════════════════════════════════════════════════

    /**
     * @notice Get the full escrow record.
     * @param escrowId The escrow to look up
     * @return The Escrow struct
     */
    function getEscrow(uint256 escrowId) external view returns (Escrow memory) {
        return escrows[escrowId];
    }

    /**
     * @notice Check if an escrow is still active.
     * @param escrowId The escrow to check
     * @return True if the escrow is in Active state
     */
    function isActive(uint256 escrowId) external view returns (bool) {
        return escrows[escrowId].state == EscrowState.Active;
    }
}
